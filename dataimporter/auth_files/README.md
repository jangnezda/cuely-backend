## Custom auth files
This directory should contain custom auth files for external service authentication such as certificates, keys, etc. Currently, this is only needed for Jira integration.

### Jira integration
Jira integration is a bit complicated, because in addition of typical oauth flow they also require creating an ssl certificate and uploading the public part to Jira web administration (then using the private key to initiate an ssl connection for oauth flows). So there are needed two files `jira.pem` and `jira.pub` in this directory for Jira integration to work. They are empty, so you will need to generate them using `openssl` tool. Please use Google for more information on Jira Oauth and SSL certificates. 
