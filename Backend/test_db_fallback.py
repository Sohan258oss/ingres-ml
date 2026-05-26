import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import SQLiteDatabase

async def run_tests():
    db_path = "ingres.db"
    if not os.path.exists(db_path):
        print(f"Error: ingres.db not found at {db_path}")
        sys.exit(1)
        
    db = SQLiteDatabase(db_path)
    
    print("Testing find_one...")
    doc = await db.assessments.find_one()
    assert doc is not None, "find_one returned None"
    assert "state" in doc, "state field missing in find_one result"
    assert "district_name" in doc, "district_name field missing in find_one result"
    print("  find_one passed:", doc)
    
    print("\nTesting distinct state...")
    states = await db.assessments.distinct("state")
    assert len(states) > 0, "distinct states list is empty"
    print("  distinct states passed:", states)
    
    print("\nTesting count_documents...")
    total_cnt = await db.assessments.count_documents({})
    assert total_cnt == 49, f"count_documents({{}}) should be 49, got {total_cnt}"
    
    over_exploited_cnt = await db.assessments.count_documents({"category": {"$regex": "^over-exploited$", "$options": "i"}})
    assert over_exploited_cnt > 0, "count of over-exploited blocks should be > 0"
    print(f"  count_documents passed: total={total_cnt}, over-exploited={over_exploited_cnt}")
    
    print("\nTesting find with limit and sort...")
    cursor = db.assessments.find().sort("extraction", -1).limit(5)
    top_5 = await cursor.to_list()
    assert len(top_5) == 5, f"limit should return 5 rows, got {len(top_5)}"
    assert top_5[0]["extraction"] >= top_5[1]["extraction"], "sort order incorrect"
    print("  find limit and sort passed:", [r["extraction"] for r in top_5])
    
    print("\nTesting aggregate distribution...")
    pipeline_dist = [
        {"$group": {"_id": "$category", "cnt": {"$sum": 1}}}
    ]
    cursor = db.assessments.aggregate(pipeline_dist)
    dist_rows = await cursor.to_list()
    assert len(dist_rows) > 0, "aggregate distribution returned no rows"
    assert "cnt" in dist_rows[0], "cnt field missing in aggregated group row"
    print("  aggregate distribution passed:", dist_rows)
    
    print("\nTesting aggregate average extraction...")
    pipeline_avg = [
        {"$match": {"state": {"$regex": "^karnataka$", "$options": "i"}}},
        {"$group": {"_id": None, "avg_extraction": {"$avg": "$extraction"}}}
    ]
    cursor = db.assessments.aggregate(pipeline_avg)
    avg_rows = await cursor.to_list()
    assert len(avg_rows) == 1, f"aggregate average should return 1 row, got {len(avg_rows)}"
    assert avg_rows[0]["avg_extraction"] > 0, "avg_extraction should be > 0"
    print("  aggregate average passed:", avg_rows)
    
    print("\nTesting aggregate comparison (nested _id)...")
    pipeline_comp = [
        {"$match": {"$or": [{"state": {"$regex": "^punjab$", "$options": "i"}}, {"district_name": {"$regex": "^punjab$", "$options": "i"}}]}},
        {"$group": {
            "_id": {"state": "$state", "district": "$district_name"},
            "avg_extraction": {"$avg": "$extraction"},
            "category": {"$first": "$category"}
        }},
        {"$limit": 1}
    ]
    cursor = db.assessments.aggregate(pipeline_comp)
    comp_rows = await cursor.to_list()
    assert len(comp_rows) == 1, f"aggregate comparison should return 1 row, got {len(comp_rows)}"
    row = comp_rows[0]
    assert isinstance(row["_id"], dict), "_id is not a dictionary"
    assert "state" in row["_id"], "nested _id missing 'state'"
    assert "district" in row["_id"], "nested _id missing 'district'"
    print("  aggregate comparison passed:", row)
    
    print("\nAll database fallback tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
