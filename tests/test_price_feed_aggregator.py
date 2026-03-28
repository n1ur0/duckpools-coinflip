"""
Tests for Price Feed Aggregator

MAT-XXX: Oracle price feed integration module with Ergo oracle pool adapter
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.price_feed_aggregator import PricePoint, PriceFeedAggregator
from backend.ergo_oracle_adapter import OracleFeed, OracleDataType, ErgoOraclePoolAdapter


class TestPricePoint:
    """Tests for PricePoint class."""

    def test_price_point_creation(self):
        """Test creating a price point."""
        price_point = PricePoint(
            price=1.23,
            timestamp=1234567890,
            source="test_oracle"
        )
        
        assert price_point.price == 1.23
        assert price_point.timestamp == 1234567890
        assert price_point.source == "test_oracle"
        assert price_point.confidence == 1.0
        assert price_point.weight == 1.0


class TestPriceFeedAggregator:
    """Tests for PriceFeedAggregator class."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock Ergo oracle pool adapter."""
        return AsyncMock(spec=ErgoOraclePoolAdapter)

    @pytest.fixture
    def aggregator(self, mock_adapter):
        """Create a price feed aggregator with mock adapter."""
        return PriceFeedAggregator(ergo_adapter=mock_adapter)

    @pytest.fixture
    def sample_feed(self):
        """Create a sample oracle feed."""
        return OracleFeed(
            name="ergo_usd",
            box_id="test_box_id",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4},
            base_asset="ERG",
            quote_asset="USD"
        )

    def test_add_price_feed(self, aggregator, sample_feed):
        """Test adding a price feed."""
        aggregator.add_price_feed(sample_feed, weight=1.0, priority=1)
        
        assert len(aggregator._feeds) == 1
        assert aggregator._feeds[0] == sample_feed
        assert aggregator._source_weights["ergo_usd"] == 1.0

    def test_add_price_feed_wrong_type(self, aggregator):
        """Test adding a non-price feed should raise error."""
        feed = OracleFeed(
            name="timestamp_feed",
            box_id="test_box_id",
            data_type=OracleDataType.TIMESTAMP,
            register_indices={"timestamp": 4}
        )
        
        with pytest.raises(ValueError, match="must be of type PRICE"):
            aggregator.add_price_feed(feed)

    def test_remove_price_feed(self, aggregator, sample_feed):
        """Test removing a price feed."""
        # Add a feed first
        aggregator.add_price_feed(sample_feed)
        assert len(aggregator._feeds) == 1
        
        # Remove it
        result = aggregator.remove_price_feed("ergo_usd")
        
        assert result is True
        assert len(aggregator._feeds) == 0
        assert "ergo_usd" not in aggregator._source_weights

    def test_remove_nonexistent_feed(self, aggregator):
        """Test removing a feed that doesn't exist."""
        result = aggregator.remove_price_feed("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_fetch_all_prices_empty(self, aggregator):
        """Test fetching prices when no feeds are configured."""
        results = await aggregator.fetch_all_prices()
        
        assert results == {}

    @pytest.mark.asyncio
    async def test_fetch_all_prices_success(self, aggregator, sample_feed):
        """Test successfully fetching prices."""
        # Add the feed
        aggregator.add_price_feed(sample_feed)
        
        # Mock the adapter response
        mock_data = {
            "feed_name": "ergo_usd",
            "box_id": "test_box_id",
            "price": 1.23,
            "timestamp": 1234567890
        }
        aggregator._ergo_adapter.get_oracle_feed_data.return_value = mock_data
        
        # Fetch prices
        results = await aggregator.fetch_all_prices()
        
        assert "ergo_usd" in results
        assert results["ergo_usd"] is not None
        assert results["ergo_usd"].price == 1.23
        assert results["ergo_usd"].source == "ergo_usd"

    @pytest.mark.asyncio
    async def test_fetch_all_prices_failure(self, aggregator, sample_feed):
        """Test handling failures when fetching prices."""
        # Add the feed
        aggregator.add_price_feed(sample_feed)
        
        # Mock the adapter to return None (failure)
        aggregator._ergo_adapter.get_oracle_feed_data.return_value = None
        
        # Fetch prices
        results = await aggregator.fetch_all_prices()
        
        assert "ergo_usd" in results
        assert results["ergo_usd"] is None

    def test_parse_price_point_success(self, aggregator, sample_feed):
        """Test successfully parsing a price point."""
        feed_data = {
            "feed_name": "ergo_usd",
            "box_id": "test_box_id",
            "price": 1.23,
            "timestamp": 1234567890
        }
        
        price_point = aggregator._parse_price_point(sample_feed, feed_data)
        
        assert price_point is not None
        assert price_point.price == 1.23
        assert price_point.timestamp == 1234567890
        assert price_point.source == "ergo_usd"

    def test_parse_price_point_no_price(self, aggregator, sample_feed):
        """Test parsing when no price is in the data."""
        feed_data = {
            "feed_name": "ergo_usd",
            "box_id": "test_box_id",
            "timestamp": 1234567890
            # Missing price
        }
        
        price_point = aggregator._parse_price_point(sample_feed, feed_data)
        
        assert price_point is None

    def test_aggregate_prices_none(self, aggregator):
        """Test aggregating when no price points are provided."""
        result = aggregator.aggregate_prices({})
        
        assert result is None

    def test_aggregate_prices_single(self, aggregator):
        """Test aggregating a single price point."""
        price_point = PricePoint(
            price=1.23,
            timestamp=1234567890,
            source="test_oracle"
        )
        
        result = aggregator.aggregate_prices({"test": price_point})
        
        assert result is not None
        assert result["price"] == 1.23
        assert result["method"] == "single_source"
        assert result["sources"] == ["test_oracle"]

    def test_aggregate_prices_mean(self, aggregator):
        """Test aggregating using mean method."""
        price_points = {
            "source1": PricePoint(price=1.0, timestamp=1, source="source1"),
            "source2": PricePoint(price=2.0, timestamp=2, source="source2"),
            "source3": PricePoint(price=3.0, timestamp=3, source="source3")
        }
        
        result = aggregator.aggregate_prices(price_points, method="mean")
        
        assert result is not None
        assert result["price"] == 2.0  # (1+2+3)/3 = 2
        assert result["method"] == "mean"
        assert result["sources"] == ["source1", "source2", "source3"]

    def test_aggregate_prices_median(self, aggregator):
        """Test aggregating using median method."""
        price_points = {
            "source1": PricePoint(price=1.0, timestamp=1, source="source1"),
            "source2": PricePoint(price=2.0, timestamp=2, source="source2"),
            "source3": PricePoint(price=3.0, timestamp=3, source="source3")
        }
        
        result = aggregator.aggregate_prices(price_points, method="median")
        
        assert result is not None
        assert result["price"] == 2.0  # Median of [1,2,3] is 2
        assert result["method"] == "median"

    def test_aggregate_prices_weighted_mean(self, aggregator):
        """Test aggregating using weighted mean method."""
        price_points = {
            "source1": PricePoint(price=1.0, timestamp=1, source="source1", weight=1.0),
            "source2": PricePoint(price=2.0, timestamp=2, source="source2", weight=2.0)
        }
        
        result = aggregator.aggregate_prices(price_points, method="weighted_mean")
        
        assert result is not None
        # Weighted mean = (1.0*1.0 + 2.0*2.0) / (1.0 + 2.0) = 5.0/3.0 ≈ 1.666...
        assert abs(result["price"] - 1.666) < 0.001
        assert result["method"] == "weighted_mean"

    def test_aggregate_prices_invalid_method(self, aggregator):
        """Test aggregating with an invalid method."""
        price_points = {
            "source1": PricePoint(price=1.0, timestamp=1, source="source1")
        }
        
        with pytest.raises(ValueError, match="Unknown aggregation method"):
            aggregator.aggregate_prices(price_points, method="invalid_method")

    def test_remove_outliers(self, aggregator):
        """Test outlier removal."""
        # Create price points with one outlier
        price_points = [
            PricePoint(price=1.0, timestamp=1, source="source1"),
            PricePoint(price=1.1, timestamp=2, source="source2"),
            PricePoint(price=10.0, timestamp=3, source="source3"),  # Outlier
            PricePoint(price=0.9, timestamp=4, source="source4")
        ]
        
        filtered_prices, filtered_points = aggregator._remove_outliers(price_points, 2.0)
        
        # Should have removed the outlier (10.0)
        assert len(filtered_prices) == 3
        assert len(filtered_points) == 3
        assert 1.0 in filtered_prices
        assert 1.1 in filtered_prices
        assert 0.9 in filtered_prices
        assert 10.0 not in filtered_prices

    def test_calculate_confidence(self, aggregator):
        """Test confidence calculation."""
        # High confidence - similar prices
        prices1 = [1.0, 1.01, 0.99]
        confidence1 = aggregator._calculate_confidence(prices1, 1.0)
        
        assert confidence1 > 0.5  # Should be high confidence
        
        # Low confidence - dispersed prices
        prices2 = [1.0, 2.0, 3.0]
        confidence2 = aggregator._calculate_confidence(prices2, 2.0)
        
        assert confidence2 < 0.5  # Should be low confidence

    @pytest.mark.asyncio
    async def test_get_aggregated_price_no_feeds(self, aggregator):
        """Test getting aggregated price when no feeds match."""
        result = await aggregator.get_aggregated_price("BTC", "USD")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_aggregated_price_success(self, aggregator, sample_feed):
        """Test successfully getting aggregated price."""
        # Add a matching feed
        aggregator.add_price_feed(sample_feed)
        
        # Mock fetch_all_prices to return test data
        test_price_point = PricePoint(
            price=1.23,
            timestamp=1234567890,
            source="ergo_usd"
        )
        
        with pytest.patch.object(aggregator, 'fetch_all_prices', return_value={"ergo_usd": test_price_point}):
            result = await aggregator.get_aggregated_price("ERG", "USD")
            
            assert result is not None
            assert result["price"] == 1.23
            assert result["base_asset"] == "ERG"
            assert result["quote_asset"] == "USD"
            assert result["method"] == "single_source"