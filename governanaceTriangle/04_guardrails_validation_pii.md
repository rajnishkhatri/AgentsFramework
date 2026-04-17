# Tutorial 4: GuardRails for Validation and PII Detection

**Duration:** ~25 minutes  
**Level:** Intermediate  
**Prerequisites:** [Tutorial 1: Explainability Fundamentals](01_explainability_fundamentals.md)

---

## Introduction

When AI agents produce outputs—whether extracting invoice data, summarizing documents, or generating customer responses—how do you ensure those outputs meet quality standards, comply with regulations, and don't leak sensitive information? **Manual review doesn't scale**, and traditional validation approaches often become maintenance nightmares as requirements evolve.

The **GuardRails** component implements the **Validation Pillar** of our explainability framework, providing declarative validators with rich trace generation for agent transparency. Inspired by [Guardrails AI](https://github.com/guardrails-ai/guardrails), this approach lets you define *what* valid output looks like rather than *how* to check it.

This tutorial teaches you how to:
1. Understand the declarative validation philosophy and its advantages over imperative validation
2. Use all 7 built-in validators for common validation patterns
3. Create custom validators for domain-specific requirements
4. Handle validation failures with appropriate actions (REJECT, FIX, ESCALATE, LOG, RETRY)
5. Use validation traces for debugging and auditing
6. Implement PII detection to protect customer privacy

> 📓 **Hands-on Notebook Available**: This tutorial has an accompanying interactive notebook
> [03_guardrails_validation_traces.ipynb](../notebooks/03_guardrails_validation_traces.ipynb) where you can
> run the code examples yourself. Start with the tutorial concepts, then practice in the notebook.

---

## 1. Declarative vs. Imperative Validation

The fundamental philosophy behind GuardRails is **declarative validation**—defining *what* constraints must be satisfied rather than *how* to check them. This distinction has profound implications for maintainability, readability, and extensibility.

### 1.1 The Imperative Approach (Traditional)

In imperative validation, you write procedural code that explicitly checks each condition:

```python
# ❌ IMPERATIVE VALIDATION - HOW to check
def validate_invoice_output(output: dict) -> tuple[bool, list[str]]:
    """Traditional imperative validation."""
    errors = []
    
    # Check required fields
    if "vendor_name" not in output:
        errors.append("Missing required field: vendor_name")
    if "invoice_number" not in output:
        errors.append("Missing required field: invoice_number")
    if "total_amount" not in output:
        errors.append("Missing required field: total_amount")
    
    # Check confidence range
    confidence = output.get("confidence")
    if confidence is not None:
        if confidence < 0.8:
            errors.append(f"Confidence {confidence} below minimum 0.8")
        if confidence > 1.0:
            errors.append(f"Confidence {confidence} above maximum 1.0")
    
    # Check for PII patterns
    output_str = str(output)
    import re
    ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
    if re.search(ssn_pattern, output_str):
        errors.append("Potential SSN detected in output")
    
    cc_pattern = r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
    if re.search(cc_pattern, output_str):
        errors.append("Potential credit card detected in output")
    
    # Check output length
    output_text = output.get("output", "")
    if len(output_text) < 10:
        errors.append("Output too short (minimum 10 characters)")
    if len(output_text) > 5000:
        errors.append("Output too long (maximum 5000 characters)")
    
    return len(errors) == 0, errors

# Usage
is_valid, errors = validate_invoice_output({"vendor_name": "Acme"})
if not is_valid:
    print(f"Validation failed: {errors}")
```

**Problems with Imperative Validation:**

| Issue | Description |
|-------|-------------|
| **Code Duplication** | Same checks repeated across different validators |
| **Hidden Logic** | Validation rules buried in procedural code |
| **Hard to Audit** | No clear documentation of what's being validated |
| **Tight Coupling** | Validation logic mixed with business logic |
| **No Trace** | No record of which checks passed/failed |
| **Difficult Updates** | Changing a rule requires modifying code |

### 1.2 The Declarative Approach (GuardRails)

In declarative validation, you describe *what* valid output looks like as data:

```python
# ✅ DECLARATIVE VALIDATION - WHAT to check
from backend.explainability.guardrails import (
    GuardRail, GuardRailValidator, BuiltInValidators, FailAction
)

# Declare validation rules as data, not code
invoice_guardrail = GuardRail(
    name="invoice_extraction_v2",
    description="Validates invoice extraction agent outputs",
    version="2.0.0",
    constraints=[
        BuiltInValidators.required_fields(["vendor_name", "invoice_number", "total_amount"]),
        BuiltInValidators.confidence_range(min_conf=0.8, max_conf=1.0),
        BuiltInValidators.no_pii(),
        BuiltInValidators.length_check(min_len=10, max_len=5000),
    ],
    on_fail_default=FailAction.REJECT,
)

# Validation execution is separate from declaration
validator = GuardRailValidator()
result = validator.validate({"vendor_name": "Acme", "confidence": 0.95, "output": "Valid invoice"}, invoice_guardrail)

print(f"Valid: {result.is_valid}")
print(f"Errors: {result.total_errors}")
for entry in result.entries:
    print(f"  {entry.constraint_name}: {'✓' if entry.passed else '✗'} {entry.message}")
```

**Advantages of Declarative Validation:**

| Benefit | Description |
|---------|-------------|
| **Self-Documenting** | Rules are readable data, not hidden in code |
| **Composable** | Mix and match validators like building blocks |
| **Auditable** | Every validation produces a detailed trace |
| **Versionable** | Track changes to validation rules over time |
| **Testable** | Validators are isolated, reusable units |
| **Configurable** | Rules can be changed without code deployment |

### 1.3 Side-by-Side Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│              IMPERATIVE vs DECLARATIVE VALIDATION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   IMPERATIVE (Traditional)                 DECLARATIVE (GuardRails)          │
│   ─────────────────────────                ─────────────────────────         │
│                                                                              │
│   def validate(output):                    guardrail = GuardRail(            │
│       errors = []                              name="invoice_v2",            │
│       if "vendor" not in output:               constraints=[                 │
│           errors.append("...")                     required_fields([...]),   │
│       if conf < 0.8:                               confidence_range(...),    │
│           errors.append("...")                     no_pii(),                 │
│       # ... more procedural code                   length_check(...),        │
│       return len(errors) == 0              ]                                 │
│                                            )                                 │
│                                                                              │
│   • HOW to check (procedural)              • WHAT to check (declarative)     │
│   • Logic scattered in code                • Rules centralized as data       │
│   • No audit trail                         • Rich validation traces          │
│   • Hard to document                       • Self-documenting                │
│   • Tight coupling                         • Loosely coupled                 │
│   • Requires code changes                  • Config-driven updates           │
│                                                                              │
│   RESULT: Works, but doesn't scale         RESULT: Maintainable at scale     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Real-World Scenario: Evolving Requirements

Consider how requirements change over time:

**Week 1**: "Validate that invoice extraction includes vendor name"
**Week 4**: "Also check for invoice number and amount"
**Week 8**: "Add PII detection for compliance"
**Week 12**: "Confidence scores must be at least 0.8"
**Week 16**: "Different rules for different document types"

**Imperative Evolution (Growing Complexity):**

```python
# Week 16: Your validation function has become unmaintainable
def validate_invoice_v4(output, doc_type, region, customer_tier):
    errors = []
    warnings = []
    
    # Original checks (Week 1-4)
    required = ["vendor_name"]
    if doc_type != "receipt":
        required.extend(["invoice_number", "total_amount"])
    
    for field in required:
        if field not in output:
            errors.append(f"Missing: {field}")
    
    # PII checks (Week 8)
    if region in ["EU", "CA"]:  # GDPR, CCPA
        if has_pii(output):
            errors.append("PII detected")
    
    # Confidence checks (Week 12) - different per customer
    min_conf = 0.9 if customer_tier == "enterprise" else 0.8
    if output.get("confidence", 0) < min_conf:
        errors.append(f"Low confidence")
    
    # ... 200 more lines of conditional logic
    return errors, warnings
```

**Declarative Evolution (Composed Guardrails):**

```python
# Week 16: Clean, composable validation rules
from backend.explainability.guardrails import GuardRail, BuiltInValidators

# Base constraints (reusable)
base_constraints = [
    BuiltInValidators.required_fields(["vendor_name"]),
    BuiltInValidators.no_pii(),
]

# Invoice-specific guardrail
invoice_guardrail = GuardRail(
    name="invoice_validator",
    description="Full invoice validation",
    constraints=base_constraints + [
        BuiltInValidators.required_fields(["invoice_number", "total_amount"]),
        BuiltInValidators.confidence_range(min_conf=0.8),
    ]
)

# Receipt guardrail (simpler)
receipt_guardrail = GuardRail(
    name="receipt_validator",
    description="Receipt validation (relaxed requirements)",
    constraints=base_constraints + [
        BuiltInValidators.confidence_range(min_conf=0.7),
    ]
)

# Enterprise guardrail (stricter)
enterprise_guardrail = GuardRail(
    name="enterprise_validator",
    description="Enterprise tier validation",
    constraints=base_constraints + [
        BuiltInValidators.required_fields(["invoice_number", "total_amount"]),
        BuiltInValidators.confidence_range(min_conf=0.9),  # Higher threshold
    ]
)

# Usage: Select appropriate guardrail
def get_guardrail(doc_type: str, customer_tier: str) -> GuardRail:
    if customer_tier == "enterprise":
        return enterprise_guardrail
    return invoice_guardrail if doc_type == "invoice" else receipt_guardrail
```

### 1.5 The Constraint Model

Every validation rule in GuardRails is represented as a `Constraint`:

```python
from backend.explainability.guardrails import Constraint, Severity, FailAction

# A Constraint defines a single validation rule
constraint = Constraint(
    name="vendor_name_required",              # Unique identifier
    description="Vendor name must be present", # Human-readable explanation
    check_fn="required",                       # Which validator to use
    params={"fields": ["vendor_name"]},        # Parameters for the validator
    severity=Severity.ERROR,                   # ERROR, WARNING, or INFO
    on_fail=FailAction.REJECT,                 # What to do if validation fails
)
```

**Constraint Fields Explained:**

| Field | Purpose | Values |
|-------|---------|--------|
| `name` | Unique identifier for this constraint | Any string |
| `description` | Human-readable explanation | Documentation string |
| `check_fn` | Validator function to execute | `length`, `pii`, `regex`, `required`, etc. |
| `params` | Parameters passed to the validator | Dict of validator-specific params |
| `severity` | How critical is this constraint | `ERROR` (blocking), `WARNING`, `INFO` |
| `on_fail` | Action when validation fails | `REJECT`, `FIX`, `ESCALATE`, `LOG`, `RETRY` |

---

## 2. Built-in Validators

GuardRails provides **7 built-in validators** covering the most common validation patterns. Each validator has a factory method for creating constraints and a check method for execution.

### 2.1 length_check — String Length Validation

Validates that a string field is within specified length bounds.

```python
from backend.explainability.guardrails import BuiltInValidators

# Create the constraint
length_constraint = BuiltInValidators.length_check(min_len=10, max_len=5000)

# The constraint configuration
print(f"Name: {length_constraint.name}")
print(f"Params: {length_constraint.params}")
# Output:
#   Name: length_check
#   Params: {'min_len': 10, 'max_len': 5000}
```

**Use Cases:**
- Ensuring agent responses aren't empty or truncated
- Preventing excessively long outputs that may indicate hallucination
- Enforcing API response size limits

**Example Validation:**

```python
guardrail = GuardRail(
    name="response_length",
    description="Validates response length",
    constraints=[BuiltInValidators.length_check(min_len=20, max_len=500)]
)

validator = GuardRailValidator()

# Too short
result = validator.validate({"output": "Hi"}, guardrail)
print(f"'Hi': {result.entries[0].message}")
# Output: 'Hi': Length 2 is below minimum 20

# Just right
result = validator.validate({"output": "Thank you for your inquiry. I'll help you with that."}, guardrail)
print(f"Valid response: {result.is_valid}")
# Output: Valid response: True

# Too long
result = validator.validate({"output": "x" * 600}, guardrail)
print(f"Long response: {result.entries[0].message}")
# Output: Long response: Length 600 exceeds maximum 500
```

### 2.2 regex_match — Pattern Matching

Validates that a field matches a regular expression pattern.

```python
# Invoice number format: INV-YYYY-NNNN
invoice_format = BuiltInValidators.regex_match(r"INV-\d{4}-\d{4}")

# Email format
email_format = BuiltInValidators.regex_match(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)

# ISO date format
date_format = BuiltInValidators.regex_match(r"\d{4}-\d{2}-\d{2}")
```

**Use Cases:**
- Validating structured identifiers (invoice numbers, order IDs)
- Ensuring extracted dates match expected formats
- Checking URL or email formats

**Example Validation:**

```python
guardrail = GuardRail(
    name="invoice_format",
    description="Validates invoice number format",
    constraints=[BuiltInValidators.regex_match(r"INV-\d{4}-\d{4}")]
)

test_cases = ["INV-2024-0001", "INV-24-001", "INVOICE-123", "inv-2024-0001"]

for invoice_num in test_cases:
    result = validator.validate({"output": invoice_num}, guardrail)
    status = "✓ MATCH" if result.is_valid else "✗ NO MATCH"
    print(f"  '{invoice_num}': {status}")

# Output:
#   'INV-2024-0001': ✓ MATCH
#   'INV-24-001': ✗ NO MATCH
#   'INVOICE-123': ✗ NO MATCH
#   'inv-2024-0001': ✗ NO MATCH (case sensitive)
```

### 2.3 no_pii — PII Detection

Detects common Personally Identifiable Information patterns in output.

```python
# Create PII detection constraint
pii_constraint = BuiltInValidators.no_pii()
```

**Detected PII Patterns:**

| PII Type | Pattern | Example |
|----------|---------|---------|
| **SSN** | `XXX-XX-XXXX` | `123-45-6789` |
| **Credit Card** | 16 digits with optional separators | `4111-1111-1111-1111` |
| **Email** | Standard email format | `user@example.com` |
| **Phone** | US phone formats | `+1-555-123-4567`, `(555) 123-4567` |

**Example Validation:**

```python
guardrail = GuardRail(
    name="pii_detector",
    description="Blocks output containing PII",
    constraints=[BuiltInValidators.no_pii()],
    on_fail_default=FailAction.REJECT
)

test_cases = [
    "Customer inquiry about order #12345",           # Clean
    "User John Smith, SSN: 123-45-6789",            # SSN detected
    "Please contact support@company.com for help",  # Email detected
    "Card ending in 4242: 4111-1111-1111-4242",     # Credit card detected
    "Call us at +1-800-555-0123",                   # Phone detected
]

for text in test_cases:
    result = validator.validate({"output": text}, guardrail)
    if result.is_valid:
        print(f"  ✓ CLEAN: {text[:50]}...")
    else:
        print(f"  ✗ PII DETECTED: {result.entries[0].message}")

# Output:
#   ✓ CLEAN: Customer inquiry about order #12345...
#   ✗ PII DETECTED: Potential SSN detected
#   ✗ PII DETECTED: Email address detected
#   ✗ PII DETECTED: Potential credit card number detected
#   ✗ PII DETECTED: Potential phone number detected
```

### 2.4 confidence_range — Numeric Range Validation

Validates that a confidence score or numeric value falls within a specified range.

```python
# High confidence required for production
high_confidence = BuiltInValidators.confidence_range(min_conf=0.9, max_conf=1.0)

# Standard confidence threshold
standard_confidence = BuiltInValidators.confidence_range(min_conf=0.7, max_conf=1.0)

# Percentage range (0-100)
percentage_check = BuiltInValidators.confidence_range(min_conf=0, max_conf=100)
```

**Use Cases:**
- Ensuring extraction confidence meets quality thresholds
- Validating probability scores from ML models
- Checking similarity scores in retrieval systems

**Example Validation:**

```python
guardrail = GuardRail(
    name="confidence_check",
    description="Requires high confidence scores",
    constraints=[BuiltInValidators.confidence_range(min_conf=0.8, max_conf=1.0)]
)

test_scores = [0.95, 0.85, 0.75, 0.50, 1.05]

for score in test_scores:
    result = validator.validate({"confidence": score}, guardrail)
    status = "✓ VALID" if result.is_valid else "✗ INVALID"
    print(f"  confidence={score}: {status} - {result.entries[0].message}")

# Output:
#   confidence=0.95: ✓ VALID - Confidence 0.95 is within range [0.8, 1.0]
#   confidence=0.85: ✓ VALID - Confidence 0.85 is within range [0.8, 1.0]
#   confidence=0.75: ✗ INVALID - Confidence 0.75 is below minimum 0.8
#   confidence=0.50: ✗ INVALID - Confidence 0.5 is below minimum 0.8
#   confidence=1.05: ✗ INVALID - Confidence 1.05 exceeds maximum 1.0
```

### 2.5 required_fields — Field Presence Validation

Validates that all specified fields are present in the input data.

```python
# Invoice extraction required fields
invoice_fields = BuiltInValidators.required_fields([
    "vendor_name", 
    "invoice_number", 
    "total_amount"
])

# Customer profile required fields
profile_fields = BuiltInValidators.required_fields([
    "customer_id",
    "email",
    "name"
])
```

**Use Cases:**
- Ensuring agent extractions include all required data
- Validating API responses have expected structure
- Checking form submissions are complete

**Example Validation:**

```python
guardrail = GuardRail(
    name="invoice_fields",
    description="Validates required invoice fields",
    constraints=[BuiltInValidators.required_fields(["vendor_name", "invoice_number", "total_amount"])]
)

test_cases = [
    {"vendor_name": "Acme", "invoice_number": "INV-001", "total_amount": 500},  # Complete
    {"vendor_name": "Acme", "total_amount": 500},                                # Missing invoice_number
    {"vendor_name": "Acme"},                                                     # Missing multiple
]

for data in test_cases:
    result = validator.validate(data, guardrail)
    if result.is_valid:
        print(f"  ✓ COMPLETE: {list(data.keys())}")
    else:
        print(f"  ✗ INCOMPLETE: {result.entries[0].message}")

# Output:
#   ✓ COMPLETE: ['vendor_name', 'invoice_number', 'total_amount']
#   ✗ INCOMPLETE: Missing required fields: invoice_number
#   ✗ INCOMPLETE: Missing required fields: invoice_number, total_amount
```

### 2.6 json_parseable — JSON Format Validation

Validates that a string field contains valid JSON.

```python
json_constraint = BuiltInValidators.json_parseable()
```

**Use Cases:**
- Validating LLM outputs that should be JSON
- Checking API responses are properly formatted
- Ensuring structured data extractions are parseable

**Example Validation:**

```python
guardrail = GuardRail(
    name="json_format",
    description="Validates JSON output",
    constraints=[BuiltInValidators.json_parseable()]
)

test_outputs = [
    '{"vendor": "Acme", "amount": 100}',        # Valid JSON
    '{"vendor": "Acme", amount: 100}',          # Invalid (unquoted key)
    'The vendor is Acme with amount $100',      # Not JSON
    '{"nested": {"deep": {"value": true}}}',    # Valid nested JSON
]

for output in test_outputs:
    result = validator.validate({"output": output}, guardrail)
    status = "✓ VALID JSON" if result.is_valid else "✗ INVALID"
    print(f"  {status}: {output[:40]}...")

# Output:
#   ✓ VALID JSON: {"vendor": "Acme", "amount": 100}...
#   ✗ INVALID: {"vendor": "Acme", amount: 100}...
#   ✗ INVALID: The vendor is Acme with amount $100...
#   ✓ VALID JSON: {"nested": {"deep": {"value": true}}}...
```

### 2.7 value_in_list — Enum Validation

Validates that a field value is one of an allowed set of values.

```python
# Document type enum
doc_type_constraint = BuiltInValidators.value_in_list(
    allowed_values=["invoice", "receipt", "contract", "statement"],
    field="document_type"
)

# Status enum
status_constraint = BuiltInValidators.value_in_list(
    allowed_values=["pending", "approved", "rejected"],
    field="status"
)

# Priority levels
priority_constraint = BuiltInValidators.value_in_list(
    allowed_values=["low", "medium", "high", "critical"],
    field="priority"
)
```

**Use Cases:**
- Validating categorical outputs from classification agents
- Ensuring status values match expected enums
- Checking extracted data matches known categories

**Example Validation:**

```python
guardrail = GuardRail(
    name="document_type",
    description="Validates document classification",
    constraints=[BuiltInValidators.value_in_list(
        allowed_values=["invoice", "receipt", "contract"],
        field="doc_type"
    )]
)

test_types = ["invoice", "receipt", "memo", "email"]

for doc_type in test_types:
    result = validator.validate({"doc_type": doc_type}, guardrail)
    status = "✓ VALID" if result.is_valid else "✗ INVALID"
    print(f"  doc_type='{doc_type}': {status}")

# Output:
#   doc_type='invoice': ✓ VALID
#   doc_type='receipt': ✓ VALID
#   doc_type='memo': ✗ INVALID
#   doc_type='email': ✗ INVALID
```

### Summary: Built-in Validators Reference

| Validator | Factory Method | Check Method | Primary Use |
|-----------|---------------|--------------|-------------|
| **length_check** | `length_check(min_len, max_len)` | `check_length()` | String length bounds |
| **regex_match** | `regex_match(pattern)` | `check_regex()` | Pattern matching |
| **no_pii** | `no_pii()` | `check_pii()` | PII detection |
| **confidence_range** | `confidence_range(min, max)` | `check_confidence()` | Numeric range |
| **required_fields** | `required_fields([fields])` | `check_required()` | Field presence |
| **json_parseable** | `json_parseable()` | `check_json()` | JSON format |
| **value_in_list** | `value_in_list(values, field)` | `check_in_list()` | Enum validation |

---

## 3. Creating Custom Validators

While built-in validators cover common patterns, you'll often need domain-specific validation. GuardRails supports custom validators through the constraint system.

### 3.1 Custom Validator Pattern

To create a custom validator, you need:
1. A factory method that creates a `Constraint`
2. A check method that returns `tuple[bool, str]`

```python
from backend.explainability.guardrails import Constraint, Severity, FailAction

class DomainValidators:
    """Custom validators for domain-specific use cases."""
    
    @staticmethod
    def medical_code_format() -> Constraint:
        """Create constraint to validate ICD-10 medical codes."""
        return Constraint(
            name="medical_code_format",
            description="ICD-10 code must match format: letter + 2 digits + optional decimal + digits",
            check_fn="medical_code",
            params={},
            severity=Severity.ERROR,
            on_fail=FailAction.REJECT,
        )
    
    @staticmethod
    def check_medical_code(
        data: dict, field: str = "output"
    ) -> tuple[bool, str]:
        """Check value matches ICD-10 format (e.g., A00.0, B99.9, Z99)."""
        import re
        value = str(data.get(field, ""))
        
        # ICD-10 pattern: letter + 2 digits + optional (dot + 1-2 digits)
        pattern = r"^[A-Z]\d{2}(\.\d{1,2})?$"
        
        if re.match(pattern, value, re.IGNORECASE):
            return True, f"Valid ICD-10 code: {value}"
        return False, f"Invalid ICD-10 format: {value} (expected: A00.0 or B99)"
```

### 3.2 Registering Custom Validators

To use custom validators with `GuardRailValidator`, you need to add the check method to the `BuiltInValidators` class or create a subclass:

```python
# Option 1: Extend BuiltInValidators
class ExtendedValidators(BuiltInValidators):
    """Extended validators with domain-specific checks."""
    
    @staticmethod
    def check_medical_code(data: dict, field: str = "output") -> tuple[bool, str]:
        """Check ICD-10 medical code format."""
        import re
        value = str(data.get(field, ""))
        pattern = r"^[A-Z]\d{2}(\.\d{1,2})?$"
        
        if re.match(pattern, value, re.IGNORECASE):
            return True, f"Valid ICD-10 code: {value}"
        return False, f"Invalid ICD-10 format: {value}"
    
    @staticmethod
    def medical_code_format() -> Constraint:
        """Factory for medical code constraint."""
        return Constraint(
            name="medical_code",
            description="Validates ICD-10 medical code format",
            check_fn="medical_code",  # Maps to check_medical_code
            params={},
            severity=Severity.ERROR,
        )
```

### 3.3 Domain-Specific Example: Financial Transaction Validation

```python
class FinancialValidators:
    """Validators for financial transaction processing."""
    
    @staticmethod
    def currency_format(allowed_currencies: list[str] = None) -> Constraint:
        """Validate currency code format (ISO 4217)."""
        if allowed_currencies is None:
            allowed_currencies = ["USD", "EUR", "GBP", "JPY", "CAD"]
        
        return Constraint(
            name="currency_format",
            description=f"Currency must be one of: {allowed_currencies}",
            check_fn="currency",
            params={"allowed": allowed_currencies},
            severity=Severity.ERROR,
        )
    
    @staticmethod
    def check_currency(
        data: dict, allowed: list[str], field: str = "currency"
    ) -> tuple[bool, str]:
        """Check currency code is valid ISO 4217."""
        value = str(data.get(field, "")).upper()
        
        if value in allowed:
            return True, f"Valid currency: {value}"
        return False, f"Invalid currency '{value}', expected one of: {allowed}"
    
    @staticmethod
    def transaction_amount_range(
        min_amount: float = 0.01,
        max_amount: float = 1_000_000
    ) -> Constraint:
        """Validate transaction amount is within acceptable range."""
        return Constraint(
            name="transaction_amount",
            description=f"Amount must be between {min_amount} and {max_amount}",
            check_fn="transaction_amount",
            params={"min_amount": min_amount, "max_amount": max_amount},
            severity=Severity.ERROR,
        )
    
    @staticmethod
    def check_transaction_amount(
        data: dict, 
        min_amount: float, 
        max_amount: float,
        field: str = "amount"
    ) -> tuple[bool, str]:
        """Check transaction amount is within range."""
        try:
            amount = float(data.get(field, 0))
        except (TypeError, ValueError):
            return False, f"Invalid amount format: {data.get(field)}"
        
        if amount < min_amount:
            return False, f"Amount ${amount:.2f} below minimum ${min_amount:.2f}"
        if amount > max_amount:
            return False, f"Amount ${amount:.2f} exceeds maximum ${max_amount:.2f}"
        
        return True, f"Valid amount: ${amount:.2f}"
```

**Usage:**

```python
# Create financial transaction guardrail
financial_guardrail = GuardRail(
    name="transaction_validator",
    description="Validates financial transactions",
    constraints=[
        BuiltInValidators.required_fields(["amount", "currency", "recipient"]),
        FinancialValidators.currency_format(["USD", "EUR", "GBP"]),
        FinancialValidators.transaction_amount_range(min_amount=1.00, max_amount=50000),
        BuiltInValidators.no_pii(),  # No account numbers in output
    ]
)
```

---

## 4. Failure Actions and Decision Matrix

When validation fails, GuardRails supports **5 different failure actions** that determine how the system should respond. Choosing the right action depends on the severity of the failure and your operational context.

### 4.1 The Five Failure Actions

```python
from backend.explainability.guardrails import FailAction

# Available failure actions
print("Failure Actions:")
print(f"  REJECT:   {FailAction.REJECT.value}")    # reject
print(f"  FIX:      {FailAction.FIX.value}")       # fix
print(f"  ESCALATE: {FailAction.ESCALATE.value}") # escalate
print(f"  LOG:      {FailAction.LOG.value}")       # log
print(f"  RETRY:    {FailAction.RETRY.value}")     # retry
```

**Detailed Descriptions:**

| Action | Behavior | When to Use |
|--------|----------|-------------|
| **REJECT** | Block the output entirely; do not proceed | Critical failures: PII detected, security violations, data corruption |
| **FIX** | Attempt automatic correction (e.g., redaction) | Fixable issues: format corrections, trimming excess whitespace |
| **ESCALATE** | Route to human review | Uncertain cases: low confidence, ambiguous content, policy edge cases |
| **LOG** | Record the failure but continue | Non-critical warnings: style guidelines, soft limits |
| **RETRY** | Re-attempt with modified parameters | Transient failures: model timeouts, temporary format issues |

### 4.2 Decision Matrix

Use this decision matrix to choose the appropriate failure action:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FAILURE ACTION DECISION MATRIX                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Validation Failure Type           Recommended Action      Severity         │
│   ───────────────────────           ──────────────────      ────────         │
│                                                                              │
│   PII detected (SSN, CC, etc.)      → REJECT               ERROR            │
│   Security violation                → REJECT               ERROR            │
│   Missing critical field            → REJECT               ERROR            │
│   Data corruption detected          → REJECT               ERROR            │
│                                                                              │
│   Fixable format issue              → FIX                  WARNING          │
│   Trailing whitespace               → FIX                  INFO             │
│   Case normalization needed         → FIX                  INFO             │
│   Minor character encoding          → FIX                  WARNING          │
│                                                                              │
│   Low confidence score              → ESCALATE             WARNING          │
│   Ambiguous classification          → ESCALATE             WARNING          │
│   Policy edge case                  → ESCALATE             WARNING          │
│   High-value transaction            → ESCALATE             INFO             │
│                                                                              │
│   Style guideline violation         → LOG                  INFO             │
│   Soft limit exceeded               → LOG                  INFO             │
│   Informational check               → LOG                  INFO             │
│   Non-critical warning              → LOG                  WARNING          │
│                                                                              │
│   Model timeout                     → RETRY                ERROR            │
│   Temporary API failure             → RETRY                ERROR            │
│   Rate limit hit                    → RETRY                WARNING          │
│   Intermittent format issue         → RETRY                WARNING          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Configuring Failure Actions

**Per-Constraint Configuration:**

```python
from backend.explainability.guardrails import Constraint, Severity, FailAction

# Critical: Must reject on PII
pii_constraint = Constraint(
    name="no_pii",
    description="Block PII in output",
    check_fn="pii",
    severity=Severity.ERROR,
    on_fail=FailAction.REJECT,  # Reject immediately
)

# Non-critical: Just log length warnings
length_warning = Constraint(
    name="preferred_length",
    description="Output should be 50-200 chars for readability",
    check_fn="length",
    params={"min_len": 50, "max_len": 200},
    severity=Severity.WARNING,
    on_fail=FailAction.LOG,  # Log but continue
)

# Medium: Escalate low confidence to human review
confidence_check = Constraint(
    name="confidence_threshold",
    description="Flag low confidence for human review",
    check_fn="confidence",
    params={"min_conf": 0.7, "max_conf": 1.0},
    severity=Severity.WARNING,
    on_fail=FailAction.ESCALATE,  # Send to human
)
```

**GuardRail Default Action:**

```python
# Set default action for the entire guardrail
guardrail = GuardRail(
    name="invoice_validator",
    description="Invoice extraction validation",
    constraints=[
        BuiltInValidators.no_pii(),       # Uses its own on_fail
        BuiltInValidators.required_fields(["vendor"]),
    ],
    on_fail_default=FailAction.REJECT,  # Default for constraints without explicit on_fail
)
```

### 4.4 Handling Actions in Code

```python
def process_with_guardrails(
    output: dict, 
    guardrail: GuardRail,
    validator: GuardRailValidator
) -> dict:
    """Process agent output with guardrail validation and action handling."""
    
    result = validator.validate(output, guardrail)
    
    if result.is_valid:
        return {"status": "accepted", "output": output}
    
    # Handle based on action taken
    action = result.action_taken
    
    if action == FailAction.REJECT:
        return {
            "status": "rejected",
            "reason": "Validation failed",
            "errors": [e.message for e in result.entries if not e.passed]
        }
    
    elif action == FailAction.ESCALATE:
        return {
            "status": "pending_review",
            "output": output,
            "review_reason": "Low confidence or ambiguous output",
            "warnings": [e.message for e in result.entries if not e.passed]
        }
    
    elif action == FailAction.LOG:
        # Log warnings but accept output
        logger.warning(f"Validation warnings: {result.total_warnings}")
        return {"status": "accepted_with_warnings", "output": output}
    
    elif action == FailAction.RETRY:
        # Retry logic would go here
        return {"status": "retry_requested", "attempt": 1}
    
    elif action == FailAction.FIX:
        # Apply fixes (e.g., redaction) - implementation specific
        fixed_output = apply_fixes(output, result.entries)
        return {"status": "fixed", "output": fixed_output}
    
    return {"status": "unknown", "output": output}
```

---

## 5. Validation Traces for Debugging

One of the most powerful features of GuardRails is **validation traces**—detailed records of every constraint check that enable debugging, auditing, and analysis.

### 5.1 Understanding ValidationResult

Every validation produces a `ValidationResult` containing:

```python
from backend.explainability.guardrails import ValidationResult

# Examine a validation result
result = validator.validate({"output": "Test data", "confidence": 0.85}, guardrail)

print("=== ValidationResult Fields ===")
print(f"guardrail_name: {result.guardrail_name}")       # Which guardrail was used
print(f"input_hash: {result.input_hash[:16]}...")       # SHA256 of input (integrity)
print(f"is_valid: {result.is_valid}")                   # Overall pass/fail
print(f"total_errors: {result.total_errors}")           # Count of ERROR severity failures
print(f"total_warnings: {result.total_warnings}")       # Count of WARNING failures
print(f"validation_time_ms: {result.validation_time_ms}")  # Duration in milliseconds
print(f"action_taken: {result.action_taken}")           # FailAction if invalid
print(f"entries: {len(result.entries)} entries")        # List of ValidationEntry
```

### 5.2 Examining Validation Entries

Each constraint check produces a `ValidationEntry`:

```python
from backend.explainability.guardrails import ValidationEntry

# Examine individual entries
for entry in result.entries:
    print(f"\n--- {entry.constraint_name} ---")
    print(f"  passed: {entry.passed}")
    print(f"  message: {entry.message}")
    print(f"  severity: {entry.severity.value}")
    print(f"  timestamp: {entry.timestamp}")
    if entry.input_excerpt:
        print(f"  input_excerpt: {entry.input_excerpt[:50]}...")
    if entry.fix_applied:
        print(f"  fix_applied: {entry.fix_applied}")
```

**Example Output:**

```
--- no_pii ---
  passed: True
  message: No PII patterns detected
  severity: error
  timestamp: 2024-11-27 14:30:25.123456+00:00

--- required_fields ---
  passed: False
  message: Missing required fields: invoice_number
  severity: error
  timestamp: 2024-11-27 14:30:25.124789+00:00
  input_excerpt: {'output': 'Test data', 'confidence': 0.85}...
```

### 5.3 Aggregating Validation Traces

The validator maintains a session trace across all validations:

```python
# Run multiple validations
validator = GuardRailValidator()

for data in test_dataset:
    validator.validate(data, guardrail)

# Get all entries from the session
trace = validator.get_validation_trace()

print(f"Total validations in session: {len(trace)}")

# Analyze pass/fail rates
passed = sum(1 for e in trace if e.passed)
failed = len(trace) - passed
print(f"Pass rate: {passed/len(trace)*100:.1f}%")

# Group by constraint name
from collections import Counter
constraint_counts = Counter(e.constraint_name for e in trace)
print("\nConstraints checked:")
for name, count in constraint_counts.most_common():
    print(f"  {name}: {count} times")

# Find recent failures
failed_entries = [e for e in trace if not e.passed][-5:]
print("\nRecent failures:")
for entry in failed_entries:
    print(f"  [{entry.severity.value}] {entry.constraint_name}: {entry.message}")
```

### 5.4 Exporting Traces for Audit

Export validation traces to JSON for compliance and analysis:

```python
from pathlib import Path

# Export to file
trace_path = Path("audit/validation_trace_2024_11_27.json")
validator.export_trace(trace_path)

# Examine exported format
import json
with open(trace_path) as f:
    exported = json.load(f)

print(f"Exported at: {exported['exported_at']}")
print(f"Entry count: {exported['entry_count']}")
print(f"Sample entry: {json.dumps(exported['entries'][0], indent=2)}")
```

**Exported Format:**

```json
{
  "exported_at": "2024-11-27T16:00:00+00:00",
  "entry_count": 150,
  "entries": [
    {
      "constraint_name": "no_pii",
      "passed": true,
      "message": "No PII patterns detected",
      "severity": "error",
      "timestamp": "2024-11-27T14:30:25.123456Z",
      "input_excerpt": null,
      "fix_applied": null
    }
  ]
}
```

### 5.5 Debugging Failed Validations

Use traces to debug validation failures:

```python
def debug_validation_failure(result: ValidationResult) -> None:
    """Print detailed debugging information for a failed validation."""
    
    if result.is_valid:
        print("✓ Validation passed - no debugging needed")
        return
    
    print("=" * 60)
    print(f"VALIDATION FAILURE DEBUG: {result.guardrail_name}")
    print("=" * 60)
    print(f"Total Errors: {result.total_errors}")
    print(f"Total Warnings: {result.total_warnings}")
    print(f"Action Taken: {result.action_taken}")
    print(f"Input Hash: {result.input_hash[:32]}...")
    
    print("\n--- Failed Constraints ---")
    for entry in result.entries:
        if not entry.passed:
            print(f"\n[{entry.severity.value.upper()}] {entry.constraint_name}")
            print(f"  Message: {entry.message}")
            print(f"  Timestamp: {entry.timestamp}")
            if entry.input_excerpt:
                print(f"  Input Sample: {entry.input_excerpt[:100]}...")
    
    print("\n--- Passed Constraints ---")
    for entry in result.entries:
        if entry.passed:
            print(f"  ✓ {entry.constraint_name}")

# Usage
result = validator.validate(problematic_data, guardrail)
debug_validation_failure(result)
```

---

## 6. Case Study: PII Redaction in Customer Service Chatbot

This case study demonstrates implementing comprehensive PII detection and redaction for a customer service chatbot that handles sensitive customer data.

### 6.1 The Scenario

**TechSupport Inc.** operates a customer service chatbot that:
- Handles account inquiries and password resets
- Processes billing questions and refund requests
- Manages subscription updates and cancellations

**Compliance Requirements:**
- No PII should appear in chatbot logs or responses
- Detected PII must be redacted before storage
- All validation decisions must be auditable
- Different PII types have different risk levels

### 6.2 PII Detection Configuration

```python
from backend.explainability.guardrails import (
    GuardRail, GuardRailValidator, BuiltInValidators, 
    Constraint, Severity, FailAction, PromptGuardRail
)
from pathlib import Path

# Create comprehensive PII detection guardrail
chatbot_pii_guardrail = GuardRail(
    name="chatbot_pii_protection",
    description="Detects and blocks PII in customer service chatbot outputs",
    version="1.2.0",
    constraints=[
        # Critical: Block SSN, credit cards (highest risk)
        Constraint(
            name="block_ssn_cc",
            description="Block Social Security Numbers and Credit Card numbers",
            check_fn="pii",
            params={},
            severity=Severity.ERROR,
            on_fail=FailAction.REJECT,
        ),
        # Also check for reasonable response length
        BuiltInValidators.length_check(min_len=1, max_len=2000),
    ],
    on_fail_default=FailAction.REJECT,
)

# Initialize validator
validator = GuardRailValidator()
```

### 6.3 Testing with Real PII Examples

Using the `pii_examples_50.json` dataset to test detection:

```python
import json

# Load test data
data_path = Path("lesson-17/data/pii_examples_50.json")
with open(data_path) as f:
    pii_examples = json.load(f)

print(f"Testing with {len(pii_examples)} PII examples\n")

# Track detection results by PII type
detection_results = {
    "ssn": {"detected": 0, "total": 0},
    "credit_card": {"detected": 0, "total": 0},
    "email": {"detected": 0, "total": 0},
    "phone": {"detected": 0, "total": 0},
}

# Test each example
for example in pii_examples:
    result = validator.validate({"output": example["text"]}, chatbot_pii_guardrail)
    
    # Check each PII type in this example
    for pii_type in example["pii_types"]:
        if pii_type in detection_results:
            detection_results[pii_type]["total"] += 1
            if not result.is_valid:
                detection_results[pii_type]["detected"] += 1

# Print detection rates
print("=== PII Detection Rates ===")
for pii_type, counts in detection_results.items():
    if counts["total"] > 0:
        rate = counts["detected"] / counts["total"] * 100
        print(f"  {pii_type}: {rate:.0f}% ({counts['detected']}/{counts['total']})")
```

**Expected Output:**

```
=== PII Detection Rates ===
  ssn: 100% (8/8)
  credit_card: 100% (12/12)
  email: 100% (18/18)
  phone: 100% (22/22)
```

### 6.4 Customer Service Workflow Integration

```python
from datetime import datetime, UTC
from typing import Optional

class ChatbotResponseValidator:
    """Validates chatbot responses before sending to customers."""
    
    def __init__(self, storage_path: Path):
        self.validator = GuardRailValidator()
        self.storage_path = storage_path
        
        # Main guardrail for chatbot responses
        self.response_guardrail = GuardRail(
            name="chatbot_response_validator",
            description="Validates customer service chatbot responses",
            version="2.0.0",
            constraints=[
                BuiltInValidators.no_pii(),
                BuiltInValidators.length_check(min_len=10, max_len=2000),
            ],
            on_fail_default=FailAction.REJECT,
        )
    
    def validate_response(
        self, 
        response: str, 
        customer_id: str,
        conversation_id: str
    ) -> dict:
        """Validate a chatbot response before delivery."""
        
        result = self.validator.validate(
            {"output": response}, 
            self.response_guardrail
        )
        
        # Build response object
        validation_response = {
            "timestamp": datetime.now(UTC).isoformat(),
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "is_safe": result.is_valid,
            "validation_time_ms": result.validation_time_ms,
        }
        
        if result.is_valid:
            validation_response["response"] = response
            validation_response["status"] = "delivered"
        else:
            # Don't deliver unsafe response
            validation_response["status"] = "blocked"
            validation_response["blocked_reason"] = [
                e.message for e in result.entries if not e.passed
            ]
            validation_response["response"] = self._get_safe_fallback()
        
        return validation_response
    
    def _get_safe_fallback(self) -> str:
        """Return a safe fallback response when PII is detected."""
        return (
            "I apologize, but I'm unable to process that request. "
            "For security reasons, please contact our support team directly "
            "at support@techsupport.com or call 1-800-TECH-SUP."
        )
    
    def get_daily_report(self) -> dict:
        """Generate daily PII detection report."""
        trace = self.validator.get_validation_trace()
        
        total = len(trace)
        blocked = sum(1 for e in trace if not e.passed)
        
        # Group blocks by constraint
        block_reasons = {}
        for entry in trace:
            if not entry.passed:
                reason = entry.constraint_name
                block_reasons[reason] = block_reasons.get(reason, 0) + 1
        
        return {
            "report_date": datetime.now(UTC).date().isoformat(),
            "total_validations": total,
            "blocked_responses": blocked,
            "block_rate": f"{blocked/total*100:.2f}%" if total > 0 else "0%",
            "block_reasons": block_reasons,
        }


# Usage example
validator_service = ChatbotResponseValidator(Path("cache/chatbot"))

# Simulate chatbot responses
test_responses = [
    "Your account balance is $1,234.56. Is there anything else I can help with?",
    "I've updated your email to john.doe@gmail.com. You'll receive a confirmation shortly.",
    "To verify your identity, please confirm your SSN ending in 6789: 123-45-6789",
    "Your refund of $50 has been processed to card ending in 4242.",
]

print("=== Chatbot Response Validation ===\n")
for response in test_responses:
    result = validator_service.validate_response(
        response=response,
        customer_id="CUST-001",
        conversation_id="CONV-123"
    )
    
    status_icon = "✓" if result["is_safe"] else "✗"
    print(f"{status_icon} [{result['status'].upper()}]")
    print(f"  Original: {response[:60]}...")
    if not result["is_safe"]:
        print(f"  Blocked: {result['blocked_reason']}")
        print(f"  Fallback: {result['response'][:60]}...")
    print()
```

### 6.5 PII Redaction Implementation

For cases where you want to fix rather than reject, implement redaction:

```python
import re
from typing import Callable

class PIIRedactor:
    """Redacts PII from text while preserving structure."""
    
    # PII patterns and their redaction strategies
    PATTERNS: list[tuple[str, str, Callable[[str], str]]] = [
        # (name, pattern, redaction_function)
        ("ssn", r"\b\d{3}-\d{2}-\d{4}\b", lambda m: "[SSN REDACTED]"),
        ("credit_card", r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", 
         lambda m: f"[CARD REDACTED ...{m.group()[-4:]}]"),
        ("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
         lambda m: "[EMAIL REDACTED]"),
        ("phone", r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
         lambda m: "[PHONE REDACTED]"),
    ]
    
    def redact(self, text: str) -> tuple[str, list[dict]]:
        """Redact all PII from text, returning redacted text and redaction log."""
        redactions = []
        redacted_text = text
        
        for pii_name, pattern, redact_fn in self.PATTERNS:
            matches = list(re.finditer(pattern, redacted_text))
            for match in reversed(matches):  # Reverse to preserve positions
                original = match.group()
                replacement = redact_fn(match)
                
                redactions.append({
                    "type": pii_name,
                    "original_position": match.start(),
                    "original_length": len(original),
                    "replacement": replacement,
                })
                
                redacted_text = (
                    redacted_text[:match.start()] + 
                    replacement + 
                    redacted_text[match.end():]
                )
        
        return redacted_text, redactions
    
    def validate_and_redact(
        self, 
        text: str, 
        validator: GuardRailValidator,
        guardrail: GuardRail
    ) -> dict:
        """Validate text and redact if PII detected."""
        
        # First, validate original
        result = validator.validate({"output": text}, guardrail)
        
        if result.is_valid:
            return {
                "status": "clean",
                "text": text,
                "redactions": [],
            }
        
        # PII detected - redact
        redacted_text, redactions = self.redact(text)
        
        # Validate redacted version
        redacted_result = validator.validate({"output": redacted_text}, guardrail)
        
        return {
            "status": "redacted" if redacted_result.is_valid else "failed",
            "original_text": text,
            "text": redacted_text,
            "redactions": redactions,
            "redaction_count": len(redactions),
        }


# Usage
redactor = PIIRedactor()

test_text = """
Customer John Smith called about order #12345.
Contact: john.smith@email.com, Phone: 555-123-4567
Payment card: 4111-1111-1111-1111
SSN for verification: 123-45-6789
"""

result = redactor.validate_and_redact(
    test_text, 
    validator, 
    chatbot_pii_guardrail
)

print("=== Redaction Result ===")
print(f"Status: {result['status']}")
print(f"Redactions made: {result['redaction_count']}")
print(f"\nRedacted text:\n{result['text']}")
```

**Output:**

```
=== Redaction Result ===
Status: redacted
Redactions made: 4

Redacted text:

Customer John Smith called about order #12345.
Contact: [EMAIL REDACTED], Phone: [PHONE REDACTED]
Payment card: [CARD REDACTED ...1111]
SSN for verification: [SSN REDACTED]
```

### 6.6 Key Takeaways

| Requirement | Implementation | Guardrails Feature |
|-------------|---------------|-------------------|
| **Block PII in responses** | `no_pii()` constraint | Built-in validator |
| **Audit all validations** | `get_validation_trace()` | Trace export |
| **Different severity levels** | `Severity.ERROR/WARNING` | Constraint severity |
| **Flexible failure handling** | `FailAction.REJECT/FIX` | Failure actions |
| **Safe fallback responses** | Custom fallback logic | Action handling |
| **PII redaction option** | `PIIRedactor` class | FIX action pattern |

---

## 7. Best Practices

### 7.1 Guardrail Design

| Practice | Rationale |
|----------|-----------|
| **Start with built-in validators** | Cover common cases before custom validators |
| **Use meaningful names** | `invoice_pii_check` > `check_1` |
| **Version your guardrails** | Track changes over time |
| **Document constraints** | Use description field extensively |
| **Compose, don't duplicate** | Reuse constraint lists across guardrails |

### 7.2 Failure Action Selection

| Practice | Rationale |
|----------|-----------|
| **Default to REJECT for security** | Fail safe, not open |
| **Use ESCALATE for uncertainty** | Human review for edge cases |
| **LOG non-critical warnings** | Don't block for style issues |
| **RETRY only for transient issues** | Don't retry fundamental failures |
| **FIX only when deterministic** | Auto-fix must be reliable |

### 7.3 Validation Traces

| Practice | Rationale |
|----------|-----------|
| **Export traces regularly** | Prevent data loss |
| **Clear traces between batches** | Avoid memory growth |
| **Include input excerpts** | Enable debugging |
| **Monitor pass rates** | Detect systemic issues |
| **Archive for compliance** | Meet audit requirements |

### 7.4 PII Detection

| Practice | Rationale |
|----------|-----------|
| **Test with real patterns** | Ensure detection works |
| **Handle false positives** | Some patterns are ambiguous |
| **Layer defenses** | Combine detection + redaction |
| **Audit all detections** | Compliance evidence |
| **Update patterns regularly** | New PII formats emerge |

---

## Next Steps

### 📓 Hands-on Practice

Ready to try these concepts yourself? The **[03_guardrails_validation_traces.ipynb](../notebooks/03_guardrails_validation_traces.ipynb)** notebook lets you:

- Create guardrails with multiple constraints
- Validate data against guardrails
- Test PII detection with real examples
- Examine validation traces
- Export traces for auditing

### Continue Learning

- **Previous Tutorial**: [Tutorial 3: AgentFacts for Governance](03_agentfacts_governance.md) — Learn about agent identity and compliance
- **Next Steps**: Explore the Phase Logger notebook for workflow tracking

---

## Summary

In this tutorial, you learned:

1. **Declarative vs. Imperative Validation** — Why declaring *what* to validate is better than coding *how*
2. **Built-in Validators** — All 7 validators: length_check, regex_match, no_pii, confidence_range, required_fields, json_parseable, value_in_list
3. **Custom Validators** — Creating domain-specific validation for financial, medical, and other use cases
4. **Failure Actions** — When to REJECT, FIX, ESCALATE, LOG, or RETRY
5. **Validation Traces** — Debugging and auditing with detailed validation records
6. **PII Detection Case Study** — Implementing comprehensive PII protection for customer service

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GUARDRAILS QUICK REFERENCE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  CREATING GUARDRAILS                   BUILT-IN VALIDATORS                   │
│  ──────────────────                    ──────────────────                    │
│  guardrail = GuardRail(                BuiltInValidators.length_check(       │
│      name="...",                           min_len=10, max_len=5000)         │
│      description="...",                BuiltInValidators.regex_match(        │
│      constraints=[...],                    r"INV-\d{4}")                     │
│      on_fail_default=FailAction.REJECT BuiltInValidators.no_pii()            │
│  )                                     BuiltInValidators.confidence_range(   │
│                                            min_conf=0.8, max_conf=1.0)       │
│  VALIDATION                            BuiltInValidators.required_fields(    │
│  ──────────                                ["vendor", "amount"])             │
│  validator = GuardRailValidator()      BuiltInValidators.json_parseable()    │
│  result = validator.validate(          BuiltInValidators.value_in_list(      │
│      data, guardrail)                      ["a", "b", "c"], field="type")    │
│                                                                              │
│  VALIDATION RESULT                     FAIL ACTIONS                          │
│  ─────────────────                     ────────────                          │
│  result.is_valid                       FailAction.REJECT   # Block output    │
│  result.total_errors                   FailAction.FIX      # Auto-correct    │
│  result.total_warnings                 FailAction.ESCALATE # Human review    │
│  result.entries                        FailAction.LOG      # Log & continue  │
│  result.action_taken                   FailAction.RETRY    # Try again       │
│                                                                              │
│  SEVERITY LEVELS                       TRACES                                │
│  ───────────────                       ──────                                │
│  Severity.ERROR   # Must pass          validator.get_validation_trace()      │
│  Severity.WARNING # Should pass        validator.export_trace(filepath)      │
│  Severity.INFO    # Informational      validator.clear_trace()               │
│                                                                              │
│  PII PATTERNS DETECTED                                                       │
│  ─────────────────────                                                       │
│  • SSN: XXX-XX-XXXX                    • Email: user@domain.com             │
│  • Credit Card: 16 digits              • Phone: +1-XXX-XXX-XXXX             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*Tutorial created as part of Lesson 17: Agent Explainability Framework*

