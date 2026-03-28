"""
Unit tests for the bets API endpoints.

Tests the /bets and /bets/stats endpoints including:
- Pagination
- Filtering by game type, result, date range
- Statistics aggregation
- Error handling
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from backend.api_server import app
from backend.app.db import Base
from backend.models.bets import Bet, GameType, BetResult

# Test database setup
TEST_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/duckpools_test"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=async_sessionmaker,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def test_db():
    """Create test database tables and clean up after tests."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
async def db_session(test_db):
    """Provide a database session for each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client(db_session):
    """Create test client with database dependency override."""
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session
    
    app.dependency_overrides["backend.app.db.get_db"] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
async def sample_bets(db_session: AsyncSession):
    """Create sample bet data for testing."""
    bets = [
        Bet(
            id="bet1",
            game_type=GameType.COINFLIP,
            player_address="9fM8mp1m7KG2yNvQj8Z2Vx4hQ5o3wK9xJ1L0aVfT6rUz",
            amount=Decimal("1.0"),
            result=BetResult.WIN,
            payout=Decimal("1.98"),
            timestamp=datetime.utcnow() - timedelta(days=1),
        ),
        Bet(
            id="bet2",
            game_type=GameType.COINFLIP,
            player_address="9fM8mp1m7KG2yNvQj8Z2Vx4hQ5o3wK9xJ1L0aVfT6rUz",
            amount=Decimal("2.0"),
            result=BetResult.LOSE,
            payout=Decimal("0.0"),
            timestamp=datetime.utcnow() - timedelta(hours=12),
        ),
        Bet(
            id="bet3",
            game_type=GameType.DICE,
            player_address="9fM8mp1m7KG2yNvQj8Z2Vx4hQ5o3wK9xJ1L0aVfT6rUz",
            amount=Decimal("1.5"),
            result=BetResult.WIN,
            payout=Decimal("3.0"),
            timestamp=datetime.utcnow() - timedelta(hours=6),
        ),
        Bet(
            id="bet4",
            game_type=GameType.PLINKO,
            player_address="9gK9nq2n8LH3zOwRk9A3WY5iR6p4xL0K2M1bWgU7sV",
            amount=Decimal("0.5"),
            result=BetResult.LOSE,
            payout=Decimal("0.0"),
            timestamp=datetime.utcnow() - timedelta(hours=3),
        ),
        Bet(
            id="bet5",
            game_type=GameType.DICE,
            player_address="9gK9nq2n8LH3zOwRk9A3WY5iR6p4xL0K2M1bWgU7sV",
            amount=Decimal("3.0"),
            result=BetResult.WIN,
            payout=Decimal("6.0"),
            timestamp=datetime.utcnow() - timedelta(hours=1),
        ),
    ]
    
    db_session.add_all(bets)
    await db_session.commit()
    
    return bets


class TestBetHistory:
    """Test cases for the /bets endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_bet_history_default(self, client: TestClient, sample_bets):
        """Test getting bet history with default parameters."""
        response = client.get("/api/bets/")
        assert response.status_code == 200
        
        data = response.json()
        assert "bets" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_count"] == 5
        assert data["total_pages"] == 1
        assert len(data["bets"]) == 5
        
        # Check ordering (newest first)
        bet_ids = [bet["id"] for bet in data["bets"]]
        assert bet_ids == ["bet5", "bet4", "bet3", "bet2", "bet1"]
    
    @pytest.mark.asyncio
    async def test_get_bet_history_pagination(self, client: TestClient, sample_bets):
        """Test pagination functionality."""
        response = client.get("/api/bets/?page=1&page_size=2")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_count"] == 5
        assert data["total_pages"] == 3
        assert len(data["bets"]) == 2
        
        # Check first page items
        bet_ids = [bet["id"] for bet in data["bets"]]
        assert bet_ids == ["bet5", "bet4"]
        
        # Get second page
        response = client.get("/api/bets/?page=2&page_size=2")
        assert response.status_code == 200
        
        data = response.json()
        assert data["page"] == 2
        assert len(data["bets"]) == 2
        
        bet_ids = [bet["id"] for bet in data["bets"]]
        assert bet_ids == ["bet3", "bet2"]
    
    @pytest.mark.asyncio
    async def test_filter_by_game_type(self, client: TestClient, sample_bets):
        """Test filtering by game type."""
        response = client.get("/api/bets/?game_type=coinflip")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["bets"]) == 2
        
        for bet in data["bets"]:
            assert bet["game_type"] == "coinflip"
    
    @pytest.mark.asyncio
    async def test_filter_by_result(self, client: TestClient, sample_bets):
        """Test filtering by result."""
        response = client.get("/api/bets/?result=win")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["bets"]) == 3
        
        for bet in data["bets"]:
            assert bet["result"] == "win"
    
    @pytest.mark.asyncio
    async def test_filter_by_player_address(self, client: TestClient, sample_bets):
        """Test filtering by player address."""
        player_address = "9gK9nq2n8LH3zOwRk9A3WY5iR6p4xL0K2M1bWgU7sV"
        response = client.get(f"/api/bets/?player_address={player_address}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total_count"] == 2
        assert len(data["bets"]) == 2
        
        for bet in data["bets"]:
            assert bet["player_address"] == player_address
    
    @pytest.mark.asyncio
    async def test_filter_by_date_range(self, client: TestClient, sample_bets):
        """Test filtering by date range."""
        start_date = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        end_date = (datetime.utcnow() - timedelta(hours=6)).isoformat()
        
        response = client.get(f"/api/bets/?start_date={start_date}&end_date={end_date}")
        assert response.status_code == 200
        
        data = response.json()
        # Should include bets from the last 24 hours to 6 hours ago
        assert data["total_count"] >= 1
    
    @pytest.mark.asyncio
    async def test_invalid_date_range(self, client: TestClient, sample_bets):
        """Test error handling for invalid date range."""
        start_date = datetime.utcnow().isoformat()
        end_date = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        
        response = client.get(f"/api/bets/?start_date={start_date}&end_date={end_date}")
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        assert "start_date must be before end_date" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_invalid_page_parameters(self, client: TestClient, sample_bets):
        """Test error handling for invalid page parameters."""
        response = client.get("/api/bets/?page=0")
        assert response.status_code == 422
        
        response = client.get("/api/bets/?page_size=101")
        assert response.status_code == 422


class TestBetStats:
    """Test cases for the /bets/stats endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_overall_stats(self, client: TestClient, sample_bets):
        """Test getting overall bet statistics."""
        response = client.get("/api/bets/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "overall" in data
        assert "by_game_type" in data
        
        overall = data["overall"]
        assert "total_bets" in overall
        assert "total_wagered" in overall
        assert "total_won" in overall
        assert "win_rate" in overall
        assert "house_profit" in overall
        
        # Check calculated values
        assert overall["total_bets"] == 5
        assert overall["total_wagered"] == "8.0"  # 1+2+1.5+0.5+3
        assert overall["total_won"] == "10.98"  # 1.98+0+3+0+6
        assert overall["win_rate"] == 0.6  # 3 wins out of 5
        assert overall["house_profit"] == "-2.98"  # 8.0 - 10.98
    
    @pytest.mark.asyncio
    async def test_get_stats_grouped_by_game_type(self, client: TestClient, sample_bets):
        """Test getting statistics grouped by game type."""
        response = client.get("/api/bets/stats?group_by=game_type")
        assert response.status_code == 200
        
        data = response.json()
        assert "overall" in data
        assert "by_game_type" in data
        assert isinstance(data["by_game_type"], list)
        assert len(data["by_game_type"]) == 3  # coinflip, dice, plinko
        
        # Check grouping
        game_types = [stat["game_type"] for stat in data["by_game_type"]]
        assert "coinflip" in game_types
        assert "dice" in game_types
        assert "plinko" in game_types
        
        # Check coinflip stats
        coinflip_stats = next(
            stat for stat in data["by_game_type"] if stat["game_type"] == "coinflip"
        )
        assert coinflip_stats["stats"]["total_bets"] == 2
        assert coinflip_stats["stats"]["win_rate"] == 0.5  # 1 win out of 2
    
    @pytest.mark.asyncio
    async def test_get_stats_with_filters(self, client: TestClient, sample_bets):
        """Test getting statistics with filters."""
        response = client.get("/api/bets/stats?game_type=coinflip")
        assert response.status_code == 200
        
        data = response.json()
        overall = data["overall"]
        assert overall["total_bets"] == 2
        assert overall["win_rate"] == 0.5
    
    @pytest.mark.asyncio
    async def test_get_stats_no_bets(self, client: TestClient, db_session: AsyncSession):
        """Test getting statistics when no bets exist."""
        # Create empty database
        response = client.get("/api/bets/stats")
        assert response.status_code == 200
        
        data = response.json()
        overall = data["overall"]
        assert overall["total_bets"] == 0
        assert overall["total_wagered"] == "0"
        assert overall["total_won"] == "0"
        assert overall["win_rate"] == 0.0
        assert overall["house_profit"] == "0"
    
    @pytest.mark.asyncio
    async def test_invalid_group_by_parameter(self, client: TestClient, sample_bets):
        """Test error handling for invalid group_by parameter."""
        response = client.get("/api/bets/stats?group_by=invalid")
        assert response.status_code == 422


class TestOpenAPIDocs:
    """Test OpenAPI documentation generation."""
    
    @pytest.mark.asyncio
    async def test_openapi_schema_includes_bets_endpoints(self, client: TestClient):
        """Test that OpenAPI schema includes bets endpoints."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        paths = schema.get("paths", {})
        
        # Check that bets endpoints are documented
        assert "/api/bets/" in paths
        assert "/api/bets/stats" in paths
        
        # Check bet history endpoint
        bet_history = paths["/api/bets/"]["get"]
        assert bet_history["summary"] == "Get paginated bet history"
        
        # Check stats endpoint
        bet_stats = paths["/api/bets/stats"]["get"]
        assert bet_stats["summary"] == "Get bet statistics"
    
    @pytest.mark.asyncio
    async def test_swagger_docs_accessible(self, client: TestClient):
        """Test that Swagger UI is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_redoc_docs_accessible(self, client: TestClient):
        """Test that ReDoc is accessible."""
        response = client.get("/redoc")
        assert response.status_code == 200