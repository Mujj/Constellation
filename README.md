Constellation
=============

<h2>Overview</h2>
Constellation.tv was a project written in PHP using a modified version of Symfony 1.4. I took the standard 
MVC Pattern and converted both controller and view layers into a widget factory, using yml page descriptors 
to collect widgets into a templated output format.

The code for this is a library (Symfony Page Widgets) located here:

https://github.com/Goldcap/Constellation/tree/master/trunk/public/lib/vendor/PageWidgets

The yml page descriptors are here:

https://github.com/Goldcap/Constellation/tree/master/trunk/public/apps/frontend/lib/pages

<h2>Other Modifications</h2>
A number of other enhancements were made to decrease the development time of the system. Among them are:

1) Addition of DAL (Data Abstraction Layer) that uses XML descriptors to run all queries, using 
multiple DB Platforms, including MySQL and SOLR. (Sorry, mostly undocumented!)

https://github.com/Goldcap/Constellation/blob/master/trunk/public/lib/vendor/wtvr/1.3/WTVRData.php

2) ORM Generator, for auto-magic reverse migration from a MySQL DB to the ORM, with custom CRUD wrapper classes.

https://github.com/Goldcap/Constellation/blob/master/trunk/public/orm.sh

3) Alternate page-level memcache plugin for use with Nginx memcached module.

https://github.com/Goldcap/Constellation/blob/master/trunk/public/lib/vendor/PageWidgets/CacheWidget.class.php

<h2>Javascript Development</h2>
Most of the JS Development was done by Matthew Lauprette, currently at AOL/Huffpo, so much of the credit for that 
is due to his hard work and contributions. 
