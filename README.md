# Odoo Yuju connector

This module implements a connection between Yuju's platform and Odoo ERP, this will allow you 
receive products and orders from Yuju into your Odoo instance and send product quantities 
or stock updates directly to your account in Yuju platform. If you wish to know more about Yuju Apps
please refer to our website.
>https://yuju.io

### version
15.0.0

### Installation
1. This module depends on _Components Events_ which is part of [_Connector Framework_](http://odoo-connector.com/). In order to install this
module the _Components Events_ modules must be installed first. There are three ways to install _Components Events_
in your odoo instance:

    * [Download Components Events](https://www.odoo.com/apps/modules/14.0/component_event/) zip file directly from  Odoo Apps store
    and uncompress file into your odoo third party addons directory.
    * Use the button **Deploy on Odoo.sh** which is located right after below Download button in [Odoo Apps store](https://www.odoo.com/apps/modules/143.0/component_event/). 
    * Clone the repository `OCA/connector` or alternatively clone only the directories: `component` and `component_event`:
    https://github.com/OCA/connector
    
    
2. Clone or download and unzip the madkting/odoo_module into your third party addons directory. https://bitbucket.org/madkting/odoo_module/src/15.0/

3. With the developer mode activated go to Apps menu and search for yuju in the search bar. If the module cannot be
found make click on "Update Apps List" into the Apps top menu and try again. If you still having problems validate that you
uncompress the module into the right directory for addons.

4. Once you found the yuju module in the apps list make click on the "Install" button.

5. When the installation is over you must create a user and define a password for it, this user is for exclusive use of Yuju.

6. Go to Settings > Manage Access rights > Your new user and make click on "Edit".

7. Go to "Application Accesses" section and in Madkting label select "madkting_api" role then save the changes.

8. Now you are ready to go to your Yuju's account and introduce your Odoo credentials and configs in order to finish the integration.


 Authors
--
[Yuju Apps development team](https://yuju.io/)

Contributors & maintainers
--
Gerardo A Lopez Vega <gerardo.lopez@yuju.io>
