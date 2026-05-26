import sqlite3
import re
import os

class SQLiteCursor:
    def __init__(self, data):
        self.data = list(data)
        self.sort_col = None
        self.sort_dir = 1
        self.limit_val = None

    def sort(self, col, direction=-1):
        self.sort_col = col
        self.sort_dir = direction
        return self

    def limit(self, count):
        self.limit_val = count
        return self

    async def to_list(self, length=None):
        res = list(self.data)
        if self.sort_col:
            # MongoDB sort direction: -1 is DESC, 1 is ASC
            def key_func(x):
                val = x.get(self.sort_col)
                if val is None:
                    return "" if self.sort_dir == 1 else "~~~~~~~~~"
                return val
            res.sort(key=key_func, reverse=(self.sort_dir == -1))
        
        limit_to = self.limit_val
        if limit_to is None and length is not None:
            limit_to = length
            
        if limit_to is not None:
            res = res[:limit_to]
        return res

def evaluate_condition(val, cond):
    if val is None:
        return False
    if isinstance(cond, dict):
        if "$regex" in cond:
            pattern = cond["$regex"]
            options = cond.get("$options", "")
            flags = re.IGNORECASE if "i" in options else 0
            try:
                return bool(re.search(pattern, str(val), flags))
            except Exception:
                return False
    return str(val).lower().strip() == str(cond).lower().strip()

def evaluate_filter(row, filter_dict):
    if not filter_dict:
        return True
    
    if "$or" in filter_dict:
        or_conds = filter_dict["$or"]
        for cond in or_conds:
            cond_matches = True
            for k, v in cond.items():
                row_key = next((rk for rk in row.keys() if rk.lower() == k.lower()), None)
                if row_key is None or not evaluate_condition(row[row_key], v):
                    cond_matches = False
                    break
            if cond_matches:
                return True
        return False
        
    for k, v in filter_dict.items():
        row_key = next((rk for rk in row.keys() if rk.lower() == k.lower()), None)
        if row_key is None or not evaluate_condition(row[row_key], v):
            return False
    return True

class SQLiteCollection:
    def __init__(self, db_path, table_name):
        self.db_path = db_path
        self.table_name = table_name

    def _load_data(self):
        if not os.path.exists(self.db_path):
            return []
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {self.table_name}")
            rows = [dict(r) for r in cursor.fetchall()]
            return rows
        except Exception as e:
            print(f"Error loading table {self.table_name} from SQLite: {e}")
            return []
        finally:
            if conn:
                conn.close()

    async def find_one(self, filter_dict=None):
        data = self._load_data()
        if not filter_dict:
            return data[0] if data else None
        for row in data:
            if evaluate_filter(row, filter_dict):
                return row
        return None

    def find(self, filter_dict=None):
        data = self._load_data()
        if filter_dict:
            filtered = [r for r in data if evaluate_filter(r, filter_dict)]
        else:
            filtered = data
        return SQLiteCursor(filtered)

    async def distinct(self, key):
        data = self._load_data()
        actual_key = None
        if data:
            actual_key = next((k for k in data[0].keys() if k.lower() == key.lower()), key)
        else:
            actual_key = key
            
        vals = set()
        for r in data:
            val = r.get(actual_key)
            if val is not None:
                vals.add(val)
        return sorted(list(vals))

    async def count_documents(self, filter_dict):
        data = self._load_data()
        if not filter_dict:
            return len(data)
        count = 0
        for r in data:
            if evaluate_filter(r, filter_dict):
                count += 1
        return count

    def aggregate(self, pipeline):
        curr_data = self._load_data()
        
        for stage in pipeline:
            if "$match" in stage:
                match_filter = stage["$match"]
                curr_data = [r for r in curr_data if evaluate_filter(r, match_filter)]
                
            elif "$group" in stage:
                group_stage = stage["$group"]
                gid = group_stage.get("_id")
                
                def get_group_key(row):
                    if gid is None:
                        return None
                    if isinstance(gid, dict):
                        gk = {}
                        for k, v in gid.items():
                            fld = v.replace("$", "")
                            row_key = next((rk for rk in row.keys() if rk.lower() == fld.lower()), fld)
                            gk[k] = row.get(row_key)
                        return frozenset(gk.items())
                    if isinstance(gid, str) and gid.startswith("$"):
                        fld = gid.replace("$", "")
                        row_key = next((rk for rk in row.keys() if rk.lower() == fld.lower()), fld)
                        return row.get(row_key)
                    return gid

                groups = {}
                for r in curr_data:
                    key = get_group_key(r)
                    if key not in groups:
                        groups[key] = []
                    groups[key].append(r)
                    
                new_data = []
                for key, group_rows in groups.items():
                    if isinstance(key, frozenset):
                        _id = dict(key)
                    else:
                        _id = key
                        
                    res_row = {"_id": _id}
                    
                    for target_col, op_dict in group_stage.items():
                        if target_col == "_id":
                            continue
                        if isinstance(op_dict, dict):
                            op = list(op_dict.keys())[0]
                            val = list(op_dict.values())[0]
                            
                            if op == "$avg":
                                fld = val.replace("$", "")
                                row_key = next((rk for rk in group_rows[0].keys() if rk.lower() == fld.lower()), fld)
                                vals = [float(gr[row_key]) for gr in group_rows if gr.get(row_key) is not None]
                                res_row[target_col] = sum(vals) / len(vals) if vals else 0
                            elif op == "$sum":
                                if val == 1:
                                    res_row[target_col] = len(group_rows)
                                else:
                                    fld = val.replace("$", "")
                                    row_key = next((rk for rk in group_rows[0].keys() if rk.lower() == fld.lower()), fld)
                                    vals = [float(gr[row_key]) for gr in group_rows if gr.get(row_key) is not None]
                                    res_row[target_col] = sum(vals)
                            elif op == "$first":
                                fld = val.replace("$", "")
                                row_key = next((rk for rk in group_rows[0].keys() if rk.lower() == fld.lower()), fld)
                                res_row[target_col] = group_rows[0].get(row_key)
                                
                    new_data.append(res_row)
                curr_data = new_data
                
            elif "$limit" in stage:
                limit_val = stage["$limit"]
                curr_data = curr_data[:limit_val]
                
        return SQLiteCursor(curr_data)

class SQLiteDatabase:
    def __init__(self, db_path):
        self.db_path = db_path
        self.assessments = SQLiteCollection(db_path, "assessments")
        self.state_trends = SQLiteCollection(db_path, "state_trends")

    def close(self):
        pass
