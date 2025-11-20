# Change Log
All notable changes to this project will be documented in this file.

## [0.1b2] - 2025-11-20
### Added
- Poll creation validation, ensuring polls cannot have fewer than 2 options or more than 10 options.
- Stronger session validation checks to ensure sessions are properly validated before processing.
- End and start time to poll repr

### Fixed
- Issue causing the On End callback to not behave as expected.
- Bug where the poll end was being scheduled twice, ensuring the callback only fires once.
- Incorrect poll object creation in poll client
