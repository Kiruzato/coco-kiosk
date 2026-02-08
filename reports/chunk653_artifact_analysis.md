# Chunk 653 Artifact Analysis Report

## Overview

Chunk 653 ("DEANS" section, pages 133-135) contains all 6 deans but with severe PDF parsing artifacts that prevent LLM extraction of Almazan and Capili.

## Identified Artifacts

### 1. MASSIVE Whitespace Runs (200+ spaces)

**Location**: Line 11

**Pattern**: >200 consecutive spaces between "Esmane" and "Rey E. Enciso"

**Impact**: Breaks text flow, separates dean name from context

**Example**:
```
Mr John Aldrin Esmane ·[200+ SPACES]Rey E. Enciso DR. LEILANI E. CAPILI
```

---

### 2. Mangled Prefix: "CHARPERSONS"

**Location**: Line 3

**Pattern**: "CHARPERSONS" instead of "CHAIRPERSONS"

**Impact**: Creates false context, mangles Almazan entry

**Example**:
```
CHARPERSONS DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd
```

Should be:
```
Dr. CHRISTINE GIL O. ALMAZAN, Dean, CASEd
```

---

### 3. Interspersed Section Headers

**Location**: Lines 5, 7

**Pattern**: Unrelated section titles mixed with dean entries

**Examples**:
- Line 5: "Student OIrganizations" (also has OCR error: "OIrganizations")
- Line 7: "9 Special Provision"

**Impact**: Disrupts dean enumeration context

---

### 4. Typo: "Direcor" 

**Location**: Line 9

**Pattern**: "Direcor" instead of "Director"

**Example**:
```
DR. LEILANI E. CAPILI & FACULTY Dean, College of Nursing & Asst. SAO Direcor
```

---

### 5. Inconsistent Spacing Around Symbols

**Location**: Line 9

**Pattern**: "Asst .SAO" (space before period, no space after)

**Example**:
```
& Asst .SAO Direcor
```

Should be:
```
& Asst. SAO Director
```

---

### 6. Unicode Bullet Character

**Location**: Line 10

**Pattern**: `\uf0b7` (private use area character, rendered as bullet)

**Example**:
```
SAS Directors · Mr John Aldrin Esmane ·
```

Should be removed or replaced with standard bullet/dash.

---

### 7. Capitalization Inconsistency

**Pattern**: Mixed casing for person titles

**Examples**:
- "DR. CHRISTINE" (all caps)
- "Dr. ERIC A." (title case)
- "Engr. NOEL" (mixed)
- "Arch. CORAZON" (mixed)

---

## Clean vs. Malformed Entries

### Clean Entries (Extracted Successfully)

```
Dr. ERIC A. MATRIANO ( College of Business & Accountancy)
Engr. NOEL H. YAP (College of Computer Studies)
Arch. CORAZON Z. GONZALES (College of Architecture)
Dr. Engr. VIVIAN E. GUTIERREZ (College of Engineering)
```

**Characteristics**:
- Single line per dean
- Clear title + name + role format
- Minimal whitespace
- No interspersed headers

### Malformed Entries (NOT Extracted)

**Almazan**:
```
CHARPERSONS DR. CHRISTINE GIL O. ALMAZAN Dean, CASEd

Student OIrganizations
```

**Issues**:
- Prefixed with "CHARPERSONS" 
- Followed by unrelated section header
- Ambiguous context

**Capili** (first occurrence):
```
DR. LEILANI E. CAPILI & FACULTY Dean, College of Nursing & Asst. SAO Direcor

SAS Directors · Mr John Aldrin Esmane ·[200+ SPACES]Rey E. Enciso DR. LEILANI E. CAPILI
```

**Issues**:
- Mixed with faculty text
- Typo: "Direcor"
- Spacing issue: "Asst .SAO"
- Second occurrence fragmented by massive whitespace

---

## Normalization Requirements

### Priority 1: Critical Fixes

1. **Collapse excessive whitespace** (>3 spaces → 1 space)
2. **Remove/replace Unicode bullets** (`\uf0b7` → ` - ` or remove)
3. **Fix "CHARPERSONS"** → Remove or fix to "CHAIRPERSONS"
4. **Fix "Direcor"** → "Director"

### Priority 2: Structural Fixes

5. **Remove interspersed section headers** from dean enumeration blocks
6. **Fix spacing around punctuation** ("Asst .SAO" → "Asst. SAO")
7. **Normalize person title casing** (all "Dr.", "Engr.", "Arch.")

### Priority 3: Polish

8. **Standardize dean entry format**: "[Title] [Full Name], Dean, [College]"
9. **Remove role descriptor fragments** ("& FACULTY", etc.)
10. **Ensure one dean per line**

---

## Expected Normalized Output

```
DEANS

Dr. CHRISTINE GIL O. ALMAZAN, Dean, CASEd

Dr. LEILANI E. CAPILI, Dean, College of Nursing & Assistant SAO Director

Dr. ERIC A. MATRIANO, Dean, College of Business & Accountancy

Engr. NOEL H. YAP, Dean, College of Computer Studies

Arch. CORAZON Z. GONZALES, Dean, College of Architecture

Dr. Engr. VIVIAN E. GUTIERREZ, Dean, College of Engineering
```

All 6 deans on separate lines with consistent formatting.
