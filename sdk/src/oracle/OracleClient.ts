/**
 * DuckPools SDK - Oracle Client
 * 
 * Client for interacting with DuckPools oracle services including
 * on-chain Ergo oracle pools and HTTP oracle endpoints.
 * 
 * MAT-XXX: Oracle price feed integration module with Ergo oracle pool adapter
 * 
 * NOTE: This module is excluded from tsconfig.json compilation until the
 * following dependencies are implemented:
 *   - src/types/oracle.ts (OracleFeed, PriceFeedData, OracleHealthStatus types)
 *   - ApiResponse type export from src/types/index.ts
 *   - DuckPoolsClient.request() HTTP method
 * See DEVOPS-5 for tracking.
 */

import type { OracleFeed, PriceFeedData, OracleHealthStatus } from '../types/oracle';
import type { ApiResponse } from '../types';
import { DuckPoolsClient } from '../client/DuckPoolsClient';

export interface OracleFeedConfig {
  /** Unique name for the feed */
  name: string;
  /** Box ID of the oracle */
  boxId: string;
  /** Type of data (price, timestamp, etc.) */
  dataType: 'price' | 'exchange_rate' | 'timestamp' | 'block_height' | 'custom';
  /** Map of field names to register indices */
  registerIndices: Record<string, number>;
  /** Description of the feed */
  description?: string;
  /** Number of decimals for numeric values */
  decimals?: number;
  /** Base asset symbol */
  baseAsset?: string;
  /** Quote asset symbol */
  quoteAsset?: string;
}

export interface OracleServiceStatus {
  /** Overall service status */
  status: 'ok' | 'stale' | 'degraded' | 'no_endpoints';
  /** Currently active endpoint */
  currentEndpoint?: string;
  /** Total number of configured endpoints */
  totalEndpoints: number;
  /** Last feed update timestamp */
  lastFeedUpdate?: string;
  /** Configuration settings */
  config: {
    staleThresholdSeconds: number;
    healthCheckIntervalSeconds: number;
    enableFailover: boolean;
  };
}

export class OracleClient {
  private client: DuckPoolsClient;

  constructor(client: DuckPoolsClient) {
    this.client = client;
  }

  /**
   * Get health status of all oracle endpoints
   */
  async getHealthStatus(): Promise<Record<string, OracleHealthStatus>> {
    const response = await this.client.request<Record<string, OracleHealthStatus>>(
      'GET',
      '/api/oracle/health'
    );
    return response.data;
  }

  /**
   * Get overall oracle service status
   */
  async getServiceStatus(): Promise<OracleServiceStatus> {
    const response = await this.client.request<OracleServiceStatus>(
      'GET',
      '/api/oracle/status'
    );
    return response.data;
  }

  /**
   * Get list of all configured oracle endpoints
   */
  async getEndpoints(): Promise<Array<{
    name: string;
    url: string;
    isPrimary: boolean;
    isCurrent: boolean;
    priority: number;
  }>> {
    const response = await this.client.request<{ endpoints: Array<any> }>(
      'GET',
      '/api/oracle/endpoints'
    );
    return response.data.endpoints;
  }

  /**
   * Create a new oracle feed configuration
   */
  async createFeed(config: OracleFeedConfig): Promise<OracleFeed> {
    const response = await this.client.request<OracleFeed>(
      'POST',
      '/api/oracle/feeds',
      config
    );
    return response.data;
  }

  /**
   * Get all configured oracle feeds
   */
  async getFeeds(): Promise<OracleFeed[]> {
    const response = await this.client.request<OracleFeed[]>(
      'GET',
      '/api/oracle/feeds'
    );
    return response.data;
  }

  /**
   * Delete an oracle feed configuration
   */
  async deleteFeed(feedName: string): Promise<void> {
    await this.client.request<void>(
      'DELETE',
      `/api/oracle/feeds/${feedName}`
    );
  }

  /**
   * Get data from an on-chain oracle feed
   */
  async getOnChainFeedData(feedName: string): Promise<any> {
    const response = await this.client.request<{ data: any }>(
      'GET',
      `/api/oracle/onchain/${feedName}`
    );
    return response.data.data;
  }

  /**
   * Get data directly from an on-chain oracle box
   */
  async getOnChainBoxData(boxId: string): Promise<any> {
    const response = await this.client.request<{ data: any }>(
      'GET',
      `/api/oracle/onchain/box/${boxId}`
    );
    return response.data.data;
  }

  /**
   * Get the latest price feed for a specific asset pair
   */
  async getPriceFeed(baseAsset: string, quoteAsset: string): Promise<PriceFeedData> {
    const response = await this.client.request<{ data: PriceFeedData }>(
      'GET',
      `/api/oracle/price/${baseAsset}/${quoteAsset}`
    );
    return response.data.data;
  }

  /**
   * Fetch data from the oracle with automatic failover
   */
  async getOracleData(
    oracleBoxId?: string,
    feedName?: string
  ): Promise<any> {
    const response = await this.client.request<{ data: any }>(
      'POST',
      '/api/oracle/data' + (oracleBoxId ? `/${oracleBoxId}` : ''),
      { feedName }
    );
    return response.data.data;
  }

  /**
   * Manually switch to a different oracle endpoint
   * 
   * Note: This requires admin API key authentication
   */
  async switchEndpoint(targetEndpointName: string): Promise<{
    message: string;
    currentEndpoint: string;
  }> {
    const response = await this.client.request<{
      message: string;
      currentEndpoint: string;
    }>(
      'POST',
      '/api/oracle/switch',
      null,
      { params: { target_endpoint_name: targetEndpointName } }
    );
    return response.data;
  }

  /**
   * Watch a price feed for changes
   */
  watchPriceFeed(
    baseAsset: string,
    quoteAsset: string,
    callback: (data: PriceFeedData) => void,
    options: {
      /** Polling interval in milliseconds (default: 30000) */
      interval?: number;
      /** Maximum number of updates to receive (default: unlimited) */
      maxUpdates?: number;
    } = {}
  ): () => void {
    const { interval = 30000, maxUpdates } = options;
    let updateCount = 0;
    let timer: NodeJS.Timeout;

    const poll = async () => {
      try {
        const data = await this.getPriceFeed(baseAsset, quoteAsset);
        callback(data);
        updateCount++;

        if (maxUpdates && updateCount >= maxUpdates) {
          stop();
          return;
        }
      } catch (error) {
        console.error('Error watching price feed:', error);
      }

      timer = setTimeout(poll, interval);
    };

    const stop = () => {
      if (timer) {
        clearTimeout(timer);
      }
    };

    // Start polling
    poll();

    return stop;
  }

  /**
   * Calculate price difference between two feeds
   */
  async calculatePriceDifference(
    baseAsset: string,
    quoteAsset: string,
    feedA?: string,
    feedB?: string
  ): Promise<{
    priceA: number;
    priceB: number;
    difference: number;
    percentageDifference: number;
  }> {
    // If specific feeds are provided, fetch them directly
    let priceA: number;
    let priceB: number;

    if (feedA) {
      const dataA = await this.getOnChainFeedData(feedA);
      priceA = dataA.price || dataA.value || 0;
    } else {
      const feedDataA = await this.getPriceFeed(baseAsset, quoteAsset);
      priceA = feedDataA.price || 0;
    }

    if (feedB) {
      const dataB = await this.getOnChainFeedData(feedB);
      priceB = dataB.price || dataB.value || 0;
    } else {
      // For the second price, we'll fetch again (in a real implementation,
      // you might want to have multiple feeds configured for the same pair)
      const feedDataB = await this.getPriceFeed(baseAsset, quoteAsset);
      priceB = feedDataB.price || 0;
    }

    const difference = priceA - priceB;
    const percentageDifference = priceA !== 0 ? (difference / priceA) * 100 : 0;

    return {
      priceA,
      priceB,
      difference,
      percentageDifference
    };
  }

  /**
   * Get multiple price feeds concurrently
   */
  async getMultiplePriceFeeds(pairs: Array<{
    baseAsset: string;
    quoteAsset: string;
  }>): Promise<Array<{
    baseAsset: string;
    quoteAsset: string;
    data: PriceFeedData;
  } | {
    baseAsset: string;
    quoteAsset: string;
    error: string;
  }>> {
    const promises = pairs.map(async ({ baseAsset, quoteAsset }) => {
      try {
        const data = await this.getPriceFeed(baseAsset, quoteAsset);
        return { baseAsset, quoteAsset, data };
      } catch (error) {
        return {
          baseAsset,
          quoteAsset,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    });

    return Promise.all(promises);
  }
}