import sqlite3
import os
import uuid
import json

DB_PATH = "./data/investors.db"

def init_investor_db():
    os.makedirs("./data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS investors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            country TEXT NOT NULL,
            sector_focus TEXT NOT NULL,
            stage_focus TEXT NOT NULL,
            investment_range TEXT NOT NULL,
            portfolio_companies TEXT,
            website TEXT,
            description TEXT
        )
    """)
    conn.commit()
    
    # Check if empty, if so, seed
    cursor.execute("SELECT COUNT(*) FROM investors")
    if cursor.fetchone()[0] == 0:
        seed_investors(conn)
        
    conn.close()

def seed_investors(conn):
    mock_investors = [
        {
            "id": str(uuid.uuid4()),
            "name": "Sequoia Capital",
            "type": "VC Firm",
            "country": "USA",
            "sector_focus": "Technology, Healthcare, Financials",
            "stage_focus": "Seed, Early Stage, Late Stage",
            "investment_range": "$1M - $100M",
            "portfolio_companies": "Apple, Google, Airbnb, Stripe",
            "website": "sequoiacap.com",
            "description": "Sequoia helps daring founders build legendary companies from idea to IPO and beyond."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Y Combinator",
            "type": "Accelerator",
            "country": "USA",
            "sector_focus": "Agnostic, B2B SaaS, AI, Consumer",
            "stage_focus": "Pre-Seed, Seed",
            "investment_range": "$500K",
            "portfolio_companies": "Stripe, Airbnb, Coinbase, DoorDash",
            "website": "ycombinator.com",
            "description": "Y Combinator provides seed funding for startups."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Andreessen Horowitz (a16z)",
            "type": "VC Firm",
            "country": "USA",
            "sector_focus": "Crypto, Enterprise, Bio, Consumer",
            "stage_focus": "Seed, Series A, Series B+",
            "investment_range": "$2M - $50M+",
            "portfolio_companies": "Facebook, Twitter, Airbnb, GitHub",
            "website": "a16z.com",
            "description": "Andreessen Horowitz is a venture capital firm that backs bold entrepreneurs building the future through technology."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Index Ventures",
            "type": "VC Firm",
            "country": "UK",
            "sector_focus": "Fintech, SaaS, E-commerce, AI",
            "stage_focus": "Seed, Series A, Series B",
            "investment_range": "$1M - $30M",
            "portfolio_companies": "Figma, Notion, Revolut, Deliveroo",
            "website": "indexventures.com",
            "description": "Index Ventures is a European venture capital firm that partners with exceptional entrepreneurs."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Techstars",
            "type": "Accelerator",
            "country": "Global",
            "sector_focus": "Agnostic",
            "stage_focus": "Pre-Seed, Seed",
            "investment_range": "$120K",
            "portfolio_companies": "SendGrid, DigitalOcean, Remitly",
            "website": "techstars.com",
            "description": "Techstars is the worldwide network that helps entrepreneurs succeed."
        }
    ]
    
    cursor = conn.cursor()
    for inv in mock_investors:
        cursor.execute("""
            INSERT INTO investors (id, name, type, country, sector_focus, stage_focus, investment_range, portfolio_companies, website, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (inv["id"], inv["name"], inv["type"], inv["country"], inv["sector_focus"], inv["stage_focus"], inv["investment_range"], inv["portfolio_companies"], inv["website"], inv["description"]))
    
    conn.commit()

def get_all_investors():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM investors")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
