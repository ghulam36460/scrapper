
### 7. `database-patterns/SKILL.md`

```markdown
# Database Patterns SKILL

**Purpose:** Provide best practices for storing scraped data reliably and efficiently in a database.

## Rules
- **Use ORM or parameterized queries:** Never concatenate raw values into SQL strings. Use an ORM (SQLAlchemy, Django ORM, etc.) or `execute(sql, params)` to prevent SQL injection.  
- **Design a clear schema:** Define tables/models for entities (e.g. `Product`, `Category`). Use clear types (e.g. VARCHAR, DECIMAL, DATE). Include indexes on lookup fields for faster queries.  
- **Transactions:** Wrap batches of inserts/updates in a transaction (`session.commit()` at end) to ensure atomicity and speed.  
- **Upserts/Dedup at DB-level:** If new scrapes may re-find old items, use `ON CONFLICT` or equivalent to update existing records rather than inserting duplicates.  
- **Normalize or serialize lists:** If a field can have multiple values (e.g. tags), either normalize into a related table or store as JSON/array type if DB supports it.  
- **Connection pooling:** Use a connection pool (built-in to most ORMs or libraries) and do not open a new DB connection for every operation.

## Examples
- **SQLAlchemy model example:**  
  ```python
  class Product(Base):
      __tablename__ = "products"
      id = Column(Integer, primary_key=True)
      name = Column(String, index=True)
      price = Column(Numeric(10,2))
      scraped_date = Column(DateTime, default=datetime.utcnow)
