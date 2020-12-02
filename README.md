Requirements: Python 3 and requirements.txt modules installed.

These scripts are setup to use shortname context namespacing.

This may be undesirable functionality for other users.

# kube_get_events
 
Will prompt you to choose cluster from kubernetes configuration files.

_syntax: ./kube_get_events.py_


# kube_get_versions

Will find all versions of kubernetes from kubernetes configuration files, references deploy_config.json for shortname context for matching development environments if needed. 

_syntax: ./kube_get_versions.py_


In the root folder there are symlinks so you can add this project to your path and use:

kge, or kgv


