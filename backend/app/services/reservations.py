from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List

from sqlalchemy import text
from app.core.database_pool import db_pool


async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Decimal:
    """
    Calculates revenue for a specific month, converting check-in dates
    to the property's local timezone before filtering.
    """
    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)

    await db_pool.initialize()

    if not db_pool.session_factory:
        raise Exception("Database pool not available")

    async with db_pool.get_session() as session:
        query = text("""
            SELECT COALESCE(SUM(r.total_amount), 0) as total
            FROM reservations r
            JOIN properties p ON r.property_id = p.id AND r.tenant_id = p.tenant_id
            WHERE r.property_id = :property_id
              AND r.tenant_id = :tenant_id
              AND (r.check_in_date AT TIME ZONE p.timezone) >= :start_date
              AND (r.check_in_date AT TIME ZONE p.timezone) < :end_date
        """)
        result = await session.execute(query, {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "start_date": start_date,
            "end_date": end_date,
        })
        row = result.fetchone()
        return Decimal(str(row.total)) if row else Decimal('0')

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        await db_pool.initialize()

        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                
                query = text("""
                    SELECT
                        r.property_id,
                        SUM(r.total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations r
                    JOIN properties p ON r.property_id = p.id AND r.tenant_id = p.tenant_id
                    WHERE r.property_id = :property_id AND r.tenant_id = :tenant_id
                    GROUP BY r.property_id
                """)
                
                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        raise
