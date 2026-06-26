import os, sys, json, asyncio
sys.path.append(os.path.abspath("."))
from text_to_sql import run_text_to_sql

async def test():
    query = "Which city produces the most toppers?"
    res = run_text_to_sql(query, "", {})
    print("SQL:", res.sql)
    print("Error:", res.error)
    print("Data:", res.data)

asyncio.run(test())
