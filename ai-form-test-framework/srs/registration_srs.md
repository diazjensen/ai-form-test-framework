# Software Requirements Specification (SRS)
## Document Ref: SRS-FORM-001: User Registration & Account Creation

### 1. Objective and Scope
This document specifies the validation requirements and business rules for the User Registration Web Form under test (`/`). The form processes user registrations and issues account identifiers upon successful client and server verification.

### 2. Functional Requirements & Form Field Specifications

#### 2.1 Full Name (`full_name`)
- **Status**: The `full_name` field is mandatory and required.
- **Data Type**: Text string.
- **Constraints**: Must be between 2 and 50 characters in length. Leading and trailing whitespace must be trimmed. Special characters and numbers are disallowed.

#### 2.2 Email Address (`email`)
- **Status**: The `email` field is mandatory and required.
- **Data Type**: Valid email format according to standard RFC-5322 (`name@domain.com`).
- **Constraints**: An email format without an '@' or domain must be rejected by both client and server validation.

#### 2.3 Age (`age`)
- **Status**: The `age` field is mandatory and required.
- **Data Type**: Numeric integer.
- **Constraints**: Age must be between 18 and 100 inclusive. Users under 18 years of age are not legally permitted to register. Values above 100 must be rejected.

#### 2.4 Password (`password`)
- **Status**: The `password` field is mandatory and required.
- **Data Type**: Password.
- **Constraints**: Must be at least 8 characters and at most 64 characters. Plaintext must never be returned in API response bodies.

#### 2.5 Phone Number (`phone`)
- **Status**: The `phone` field is optional.
- **Data Type**: Numeric / international phone string.
- **Constraints**: When provided, the phone number must consist of between 10 and 13 digits with optional '+' prefix.

---

### 3. Requirements Summary Table

| Field Name | Type | Required | Minimum Length / Bound | Maximum Length / Bound | Format / Pattern |
|------------|------|----------|------------------------|------------------------|------------------|
| full_name  | text | Yes      | 2 characters           | 50 characters          | Standard text    |
| email      | email| Yes      | N/A                    | N/A                    | Valid email      |
| age        | number| Yes     | 18                     | 100                    | Positive integer |
| password   | password| Yes   | 8 characters           | 64 characters          | Secure string    |
| phone      | text | No       | 10 digits              | 13 digits              | Phone format     |

### 4. Expected Responses
- When all validation rules are met: The server responds with HTTP 200/201 and message: `"Registration successful."`.
- When any required field is omitted or violated: The server responds with HTTP 400 and an error dictionary specifying the invalid field(s).
