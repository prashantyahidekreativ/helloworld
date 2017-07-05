Print Aeroo Reports by URL
==========================

Print Aeroo Reports directly from /report/pdf/<report name>/<id> URL.
If the selected report was already printed and attached to the object, this attachment will be used.
When report was never printed or will not be attached to the object, the report is generated directly on request.

.. contents:: Table of Content
   :depth: 2

The following chapters will give you some inputs about configuration and usage of the features:

PDF Support
-----------

Usage
^^^^^

To open an Aeroo Report as PDF directly from an URL, use this scheme:

.. code-block:: html

    <a href="/report/pdf/<report_name>/<res_id>

Todo's
------

- Allow direct call for other types (doc, xls, ods, ...)

Changelog
---------

Release 0.1
^^^^^^^^^^^

Features:
~~~~~~~~~

- PDF Support

Bugfixes:
~~~~~~~~~

- no bugs found yet