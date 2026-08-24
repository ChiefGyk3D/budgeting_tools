# Project conventions

## Licensing

**Default across ChiefGyk3D's projects: GPL v3**, unless a project states otherwise.

**This project is the exception: Apache License 2.0.** The tools are meant to be
usable inside commercial products, and a copyleft license would oblige adopters
to open-source their own work. Apache 2.0 also carries an explicit patent grant.

Do not change the license of this repository without asking.

When adding a new project for this owner, apply GPL v3 unless told otherwise,
and ask before choosing anything else.

## Code

- `finplan/core/` is pure and side-effect free. Add a test alongside any change
  there; that separation is the reason the maths is testable without the CLI.
- Money is `Decimal` everywhere, never `float`.
- Every command states which rate convention it uses (nominal vs effective).
- Run `python -m pytest` before pushing.
