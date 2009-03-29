<?php

#
# XiVO Web-Interface
# Copyright (C) 2009  Proformatique <technique@proformatique.com>
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

$act = isset($_QR['act']) === true ? $_QR['act'] : '';
$page = isset($_QR['page']) === true ? xivo_uint($_QR['page'],1) : 1;

$param = array();
$param['act'] = 'list';

$logfiles = &$ipbx->get_module('logfiles');

switch($act)
{
	case 'download':
		$param['page'] = $page;

		if(isset($_QR['id']) === false || ($info = $logfiles->get($_QR['id'])) === false)
			$_QRY->go($_HTML->url('service/ipbx/control_system/logfiles'),$param);

		$file = new xivo_file();

		if(($file->download($info['file'])) === false)
			$_QRY->go($_HTML->url('service/ipbx/control_system/logfiles'),$param);

		die();
		break;
	default:
		$act = 'list';
		$total = 0;

		if(($files = $logfiles->get_list()) !== false)
		{
			$total = count($files);
			xivo::load_class('xivo_sort');
			$sort = new xivo_sort(array('key' => 'name'));
			usort($files,array(&$sort,'strnat_usort'));
		}

		$_HTML->set_var('pager',xivo_calc_page($page,20,$total));
		$_HTML->set_var('list',$files);
}

$_HTML->set_var('act',$act);

$menu = &$_HTML->get_module('menu');
$menu->set_top('top/user/'.$_USR->get_info('meta'));
$menu->set_left('left/service/ipbx/'.$ipbx->get_name());

$_HTML->set_bloc('main','service/ipbx/'.$ipbx->get_name().'/control_system/logfiles/'.$act);
$_HTML->set_struct('service/ipbx/'.$ipbx->get_name());
$_HTML->display('index');

?>