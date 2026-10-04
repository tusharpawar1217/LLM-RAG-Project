"""
Test script to verify Docker services are running correctly
"""
import sys

def test_postgres():
    """Test PostgreSQL connection"""
    try:
        import asyncpg
        import asyncio
        
        async def check():
            conn = await asyncpg.connect(
                host='localhost',
                port=5432,
                user='askdocs_user',
                password='dev_password_123',
                database='askdocs_dev'
            )
            result = await conn.fetchval('SELECT version()')
            await conn.close()
            return result
        
        result = asyncio.run(check())
        print("✅ PostgreSQL: Connected successfully")
        print(f"   Version: {result.split(',')[0]}")
        return True
    except ImportError:
        print("❌ PostgreSQL: asyncpg not installed (pip install asyncpg)")
        return False
    except Exception as e:
        print(f"❌ PostgreSQL: Connection failed - {e}")
        return False


def test_redis():
    """Test Redis connection"""
    try:
        import redis
        
        client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        client.ping()
        info = client.info('server')
        print("✅ Redis: Connected successfully")
        print(f"   Version: {info.get('redis_version', 'unknown')}")
        return True
    except ImportError:
        print("❌ Redis: redis library not installed (pip install redis)")
        return False
    except Exception as e:
        print(f"❌ Redis: Connection failed - {e}")
        return False


def test_qdrant():
    """Test Qdrant connection"""
    try:
        import requests
        
        response = requests.get('http://localhost:6333/health')
        if response.status_code == 200:
            print("✅ Qdrant: Connected successfully")
            print(f"   Status: {response.json()}")
            return True
        else:
            print(f"❌ Qdrant: Health check failed - Status {response.status_code}")
            return False
    except ImportError:
        print("❌ Qdrant: requests library not installed (pip install requests)")
        return False
    except Exception as e:
        print(f"❌ Qdrant: Connection failed - {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("AskDocs Docker Services Test")
    print("=" * 60)
    print()
    
    results = {
        "PostgreSQL": test_postgres(),
        "Redis": test_redis(),
        "Qdrant": test_qdrant()
    }
    
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for service, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {service}")
    
    print()
    print(f"Result: {passed}/{total} services operational")
    
    sys.exit(0 if passed == total else 1)
