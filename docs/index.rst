Contacts API Documentation
==========================

Welcome to the Contacts API documentation. This API provides a REST interface
for managing contacts with full authentication, authorization, and role-based
access control.

Features
--------

- **JWT Authentication**: Secure token-based authentication
- **Email Verification**: Users must verify email before accessing the API
- **Password Reset**: Email-based password reset flow
- **Role-Based Access**: User and Admin roles with different permissions
- **Redis Caching**: User data cached for performance
- **Contact Management**: Full CRUD operations with search and pagination
- **Birthday Reminders**: Find contacts with upcoming birthdays

Quick Start
-----------

1. Register a new account: ``POST /api/auth/register``
2. Verify your email using the link sent to your inbox
3. Login to get JWT token: ``POST /api/auth/login``
4. Use the token in requests: ``Authorization: Bearer <token>``

API Modules
-----------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

