<?php

#
# XiVO Web-Interface
# Copyright (C) 2006, 2007, 2008  Proformatique <technique@proformatique.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

require_once('xivo.php');

if(xivo_user::chk_authorize('root') === false)
	$_QRY->go($_HTML->url('xivo'));

$dhtml = &$_HTML->get_module('dhtml');
$dhtml->set_css('css/xivo/configuration.css');

$application = $_HTML->get_application('xivo/configuration',2);

if($application === false)
	$_QRY->go($_HTML->url('xivo'));

die(include($application));

?>
