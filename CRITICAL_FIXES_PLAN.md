# Critical Fixes Implementation Plan

## Issues Identified

### 1. **Data Loss - Results Not Saved Properly**
- **Root Cause**: Records are stored in memory-based RuntimeState and may not persist
- **Fix**: Ensure all records are written to CSV and JSON, implement proper persistence

### 2. **Missing Critical Fields in CSV Export (Phone, WhatsApp, Email, Socials, Website)**
- **Root Cause**: CSV export may not include all enriched fields
- **Fix**: Update CSV export to include all contact fields and social media links

### 3. **E-commerce Platform Detection Not Working**
- **Root Cause**: System doesn't detect Amazon, eBay, Alibaba store profiles
- **Fix**: Add platform-specific extractors for marketplace profiles and social media fallback

### 4. **Max Mode and High Stealth Mode Skipping Results**
- **Root Cause**: Aggressive filtering and confidence thresholds skip valid records
- **Fix**: Adjust confidence thresholds and ensure partial records are saved

### 5. **Download Tools Not Working or Integrated**
- **Root Cause**: Tools in Download folder run independently, no data merging
- **Fix**: Integrate Download tools into main pipeline with unified CSV output

### 6. **LLM Configuration Not Working**
- **Root Cause**: LLM provider settings may not be properly applied
- **Fix**: Fix LLM client initialization and provider routing

##Human: continue