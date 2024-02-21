# djangoToDBML
This python script creates DBML code from Django models for drawing database diagram.

The script is for a service in https://dbdiagram.io to create DBML code for 
drawing db design and reading Django's models.py for generating database 
model of it, over schema limits.

Usage:
    `python3 gen_code_for_dbdiagamio.py [-s] [-c views starting tag] [--user=django-user-table] models-file`

The models which are database views should be placed to the end of the models file using one 
tag for start. After that all the other views until the end are considered as views and the view models
are commented, not to show in the service.
