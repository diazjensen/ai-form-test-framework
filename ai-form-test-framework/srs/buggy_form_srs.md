# Software Requirements Specification (SRS): Buggy User Registration Form

## 1. Scope & Objective
This specification defines the functional contract for the user registration form available at `/buggy-form`.

## 2. Field Specifications & Constraints

| Field Name | Type | Required | Min Len | Max Len | Min Value | Max Value | Pattern / Format | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `username` | text | Yes | 3 | 20 | - | - | `^[a-zA-Z0-9_]{3,20}$` | User handle (must be mandatory). |
| `email` | email | Yes | - | - | - | - | Standard email | Contact email address. |
| `age` | number | Yes | - | - | 18 | 100 | Integer | Legal adult age (minimum 18, maximum 100). |
| `password` | password | Yes | 8 | 64 | - | - | Alphanumeric | Account secret password. |

## 3. Business Rules
1. Every fully compliant registration payload meeting all constraints MUST be accepted with HTTP 200/201.
2. The `username` field is mandatory; blank values MUST be rejected with HTTP 400.
3. The legal registration age threshold is strictly 18; applicants aged 18, 19, or 20 MUST be accepted.
4. Passwords meeting the minimum length of 8 characters MUST be processed without server crashes or 500 exceptions.
