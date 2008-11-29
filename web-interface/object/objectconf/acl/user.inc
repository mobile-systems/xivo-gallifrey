<?php

$array = array();
$array['tree'] = array();
$array['tree']['service'] = array();

$array['tree']['service']['ipbx'] = array();

$array['tree']['service']['ipbx']['general_settings'] = array();
$array['tree']['service']['ipbx']['general_settings']['sip'] = true;
$array['tree']['service']['ipbx']['general_settings']['iax'] = true;
$array['tree']['service']['ipbx']['general_settings']['voicemail'] = true;
$array['tree']['service']['ipbx']['general_settings']['phonebook'] = true;
$array['tree']['service']['ipbx']['general_settings']['advanced'] = true;

$array['tree']['service']['ipbx']['pbx_settings'] = array();
$array['tree']['service']['ipbx']['pbx_settings']['agents'] = true;
$array['tree']['service']['ipbx']['pbx_settings']['users'] = true;
$array['tree']['service']['ipbx']['pbx_settings']['groups'] = true;
$array['tree']['service']['ipbx']['pbx_settings']['queues'] = true;
$array['tree']['service']['ipbx']['pbx_settings']['meetme'] = true;
$array['tree']['service']['ipbx']['pbx_settings']['voicemail'] = true;

$array['tree']['service']['ipbx']['call_management'] = array();
$array['tree']['service']['ipbx']['call_management']['incall'] = true;
$array['tree']['service']['ipbx']['call_management']['outcall'] = true;
$array['tree']['service']['ipbx']['call_management']['rightcall'] = true;
$array['tree']['service']['ipbx']['call_management']['callfilter'] = true;
$array['tree']['service']['ipbx']['call_management']['schedule'] = true;
$array['tree']['service']['ipbx']['call_management']['voicemenu'] = true;
$array['tree']['service']['ipbx']['call_management']['cdr'] = true;

$array['tree']['service']['ipbx']['trunk_management'] = array();
$array['tree']['service']['ipbx']['trunk_management']['sip'] = true;
$array['tree']['service']['ipbx']['trunk_management']['iax'] = true;
$array['tree']['service']['ipbx']['trunk_management']['custom'] = true;

$array['tree']['service']['ipbx']['pbx_services'] = array();
$array['tree']['service']['ipbx']['pbx_services']['sounds'] = true;
$array['tree']['service']['ipbx']['pbx_services']['musiconhold'] = true;
$array['tree']['service']['ipbx']['pbx_services']['extenfeatures'] = true;
$array['tree']['service']['ipbx']['pbx_services']['handynumbers'] = true;
$array['tree']['service']['ipbx']['pbx_services']['phonebook'] = true;

$array['tree']['service']['ipbx']['system_management'] = array();
$array['tree']['service']['ipbx']['system_management']['configfiles'] = true;
$array['tree']['service']['ipbx']['system_management']['context'] = true;
$array['tree']['service']['ipbx']['system_management']['ldapfilter'] = true;

$array['tree']['service']['ipbx']['control_system'] = array();
$array['tree']['service']['ipbx']['control_system']['reload'] = true;
$array['tree']['service']['ipbx']['control_system']['restart'] = true;


$array['group'] = array();
$array['group']['visitor'] = false;

$array['group']['user'] = array();
$array['group']['user']['service'] = false;

$array['group']['admin'] = array();
$array['group']['admin']['service'] = false;

$array['group']['root'] = true;

?>