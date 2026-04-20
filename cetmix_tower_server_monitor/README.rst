==========================
Cetmix Tower Server Monitor
==========================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-cetmix%2Fcetmix--tower-lightgray.png?logo=github
    :target: https://github.com/cetmix/cetmix-tower
    :alt: cetmix/cetmix-tower

|badge1| |badge2| |badge3|

Summary
=======

Adds resource monitoring (RAM, SSD, CPU) to servers managed by Cetmix Tower, integrated visuals into the Kanban and Form views.

**Table of contents**

.. contents::
   :local:

Installation
============

To install this module, you need to:

1. Clone cetmix-tower repository.
2. Install this module `cetmix_tower_server_monitor` into your Odoo instance.

Configuration
=============

To configure this module, you need to:

1. Go to Tower > Servers.
2. Open a Server.
3. Switch to 'Monitoring' tab.
4. Set 'Monitoring Mode' to 'Pull (SSH)' and configure thresholds.

Usage
=====

The system will periodically fetch metrics via SSH (if pull is enabled). 
You can view the metrics directly on the server's Kanban card as progress bars.
Alerts will be triggered if thresholds are exceeded.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/cetmix/cetmix-tower/issues>`_.

Credits
=======

Authors
~~~~~~~

* Cetmix
* Crumges

Maintainers
~~~~~~~~~~~

This module is maintained by the Cetmix team.
