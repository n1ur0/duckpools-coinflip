"""
Tests for Oracle Cache

MAT-XXX: Oracle price feed integration module with Ergo oracle pool adapter
"""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from backend.oracle_cache import CacheEntry, OracleCache


class TestCacheEntry:
    """Tests for CacheEntry class."""

    def test_cache_entry_creation(self):
        """Test creating a cache entry."""
        data = {"price": 1.23, "timestamp": 1234567890}
        entry = CacheEntry(data=data)
        
        assert entry.data == data
        assert entry.ttl_seconds == 60
        assert isinstance(entry.timestamp, float)
        assert not entry.is_expired()
        assert entry.age_seconds() >= 0

    def test_cache_entry_expired(self):
        """Test cache entry expiration."""
        data = {"price": 1.23}
        entry = CacheEntry(data=data, ttl_seconds=0)
        
        # Should be expired immediately
        assert entry.is_expired()
        
    def test_cache_entry_not_expired(self):
        """Test cache entry not expired."""
        data = {"price": 1.23}
        entry = CacheEntry(data=data, ttl_seconds=60)
        
        # Should not be expired
        assert not entry.is_expired()


class TestOracleCache:
    """Tests for OracleCache class."""

    @pytest.fixture
    def cache(self):
        """Create a test oracle cache."""
        return OracleCache(
            default_ttl_seconds=60,
            max_cache_size=10,
            cleanup_interval_seconds=1
        )

    @pytest.fixture
    async def started_cache(self, cache):
        """Create and start a test oracle cache."""
        await cache.start()
        yield cache
        await cache.stop()

    @pytest.mark.asyncio
    async def test_cache_start_stop(self, cache):
        """Test starting and stopping the cache."""
        # Cache should not have a cleanup task initially
        assert cache._cleanup_task is None
        
        # Start the cache
        await cache.start()
        assert cache._cleanup_task is not None
        
        # Stop the cache
        await cache.stop()
        assert cache._cleanup_task is None

    @pytest.mark.asyncio
    async def test_cache_put_get(self, started_cache):
        """Test putting and getting data from cache."""
        from backend.ergo_oracle_adapter import OracleFeed, OracleDataType
        
        feed = OracleFeed(
            name="test_feed",
            box_id="test_box_id",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        data = {"price": 1.23, "timestamp": 1234567890}
        
        # Put data in cache
        started_cache.put(feed, data)
        
        # Get data from cache
        cached_data = started_cache.get(feed)
        
        assert cached_data == data
        assert started_cache._stats['hits'] == 1
        assert started_cache._stats['misses'] == 0

    @pytest.mark.asyncio
    async def test_cache_miss(self, started_cache):
        """Test cache miss."""
        from backend.ergo_oracle_adapter import OracleFeed, OracleDataType
        
        feed = OracleFeed(
            name="test_feed",
            box_id="test_box_id",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        # Get data that's not in cache
        cached_data = started_cache.get(feed)
        
        assert cached_data is None
        assert started_cache._stats['hits'] == 0
        assert started_cache._stats['misses'] == 1

    @pytest.mark.asyncio
    async def test_cache_expired_entry(self, started_cache):
        """Test that expired entries are not returned."""
        from backend.ergo_oracle_adapter import OracleFeed, OracleDataType
        
        feed = OracleFeed(
            name="test_feed",
            box_id="test_box_id",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        data = {"price": 1.23}
        
        # Put data in cache with very short TTL
        started_cache.put(feed, data, ttl_seconds=0)
        
        # Wait a tiny bit to ensure expiration
        await asyncio.sleep(0.01)
        
        # Get data - should be None due to expiration
        cached_data = started_cache.get(feed)
        
        assert cached_data is None
        assert started_cache._stats['hits'] == 0
        assert started_cache._stats['misses'] == 1
        assert started_cache._stats['expired'] == 1

    @pytest.mark.asyncio
    async def test_cache_invalidate(self, started_cache):
        """Test cache invalidation."""
        from backend.ergo_oracle_adapter import OracleFeed, OracleDataType
        
        feed = OracleFeed(
            name="test_feed",
            box_id="test_box_id",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        data = {"price": 1.23}
        
        # Put data in cache
        started_cache.put(feed, data)
        
        # Verify it's there
        cached_data = started_cache.get(feed)
        assert cached_data == data
        
        # Invalidate the entry
        started_cache.invalidate(feed)
        
        # Verify it's gone
        cached_data = started_cache.get(feed)
        assert cached_data is None

    @pytest.mark.asyncio
    async def test_cache_clear(self, started_cache):
        """Test clearing the cache."""
        from backend.ergo_oracle_adapter import OracleFeed, OracleDataType
        
        feed1 = OracleFeed(
            name="test_feed1",
            box_id="test_box_id1",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        feed2 = OracleFeed(
            name="test_feed2",
            box_id="test_box_id2",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        # Put data in cache
        started_cache.put(feed1, {"price": 1.23})
        started_cache.put(feed2, {"price": 4.56})
        
        # Verify cache has entries
        assert len(started_cache._cache) == 2
        
        # Clear cache
        started_cache.clear()
        
        # Verify cache is empty
        assert len(started_cache._cache) == 0

    @pytest.mark.asyncio
    async def test_cache_eviction(self, started_cache):
        """Test cache eviction when size limit is reached."""
        from backend.ergo_oracle_adapter import OracleFeed, OracleDataType
        
        started_cache._max_cache_size = 2  # Very small size for testing
        
        feed1 = OracleFeed(
            name="test_feed1",
            box_id="test_box_id1",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        feed2 = OracleFeed(
            name="test_feed2",
            box_id="test_box_id2",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        feed3 = OracleFeed(
            name="test_feed3",
            box_id="test_box_id3",
            data_type=OracleDataType.PRICE,
            register_indices={"price": 4}
        )
        
        # Put data in cache - should fit
        started_cache.put(feed1, {"price": 1.23})
        started_cache.put(feed2, {"price": 4.56})
        
        assert len(started_cache._cache) == 2
        assert started_cache._stats['evicted'] == 0
        
        # Put one more - should trigger eviction
        started_cache.put(feed3, {"price": 7.89})
        
        # Should still be at size limit
        assert len(started_cache._cache) <= 2
        assert started_cache._stats['evicted'] > 0

    def test_cache_stats(self, cache):
        """Test cache statistics."""
        # Initially empty
        stats = cache.get_stats()
        assert stats['size'] == 0
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['hit_rate'] == 0

    def test_cache_info(self, cache):
        """Test cache information."""
        # Initially empty
        info = cache.get_cache_info()
        assert info['entries'] == []
        assert 'stats' in info