<?php

#
# XiVO Web-Interface
# Copyright (C) 2006-2009  Proformatique <technique@proformatique.com>
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

$phonebook = &$ipbx->get_appcustom('webservices','phonebook');

if(isset($_SERVER['REMOTE_ADDR']) === false
|| $phonebook->chk_host_access($_SERVER['REMOTE_ADDR']) === false)
	xivo_die('Error/403');

$pos = isset($_QR['pos']) === true ? xivo_uint($_QR['pos']) : 0;
$node = isset($_QR['node']) === true ? xivo_uint($_QR['node']) : 0;
$directory = isset($_QR['directory']) === true && $node === 1 ? true : false;
$vendor = isset($_QR['vendor']) === true ? $phonebook->chk_vendor($_QR['vendor']) : false;

if($vendor === false && ($vendor = $phonebook->get_vendor_from_useragent()) === false)
	xivo_die('Error/Invalid Vendor and User-Agent');

$path = '/bloc/service/ipbx/'.$ipbx->get_name().'/web_services/phonebook';

if($vendor !== 'polycom')
	$displaypath = $path.'/phone';
else
	$displaypath = '/struct/service/ipbx/'.$ipbx->get_name().'/web_services/phonebook/polycom';

$_HTML->set_var('path',$path);
$_HTML->set_var('vendor',$vendor);

if(isset($_QR['name']) === false || xivo_haslen($_QR['name']) === false)
{
	if($vendor === 'aastra' || $vendor === 'polycom' || $vendor === 'snom')
		$_HTML->set_var('act','input');
	else
		$_HTML->set_var('act','directory');

	$_HTML->display($displaypath);

	die();
}

$rs = array();

if(($rsp = $phonebook->get_phonebook_search($_QR['name'])) !== false)
	$rs = $rsp;

if(($rsu = $phonebook->get_user_search($_QR['name'],false)) !== false)
	$rs = array_merge($rs,$rsu);

$url = $_HTML->url('service/ipbx/web_services/phonebook/local').
       '?'.'name='.$_QR['name'].'&vendor='.$vendor;

if(($rsx = $phonebook->get_phonebook_search_from_xivoserver($url,false)) !== false)
	$rs = array_merge($rs,$rsx);

if(($rsl = $phonebook->get_phonebook_search_from_ldapfilter($_QR['name'],false)) !== false)
	$rs = array_merge($rs,$rsl);

if(($nb = count($rs)) === 0 || $nb <= 16)
{
	$_HTML->set_var('list',$rs);
	$_HTML->set_var('prevpos',0);
	$_HTML->set_var('act','directory');
	$_HTML->display($displaypath);
	die();
}

$maxnode = (int) floor(log($nb,16));

if($node === 0 || $node > $maxnode)
{
	$node = $maxnode;
	$beg = $prevpos = 0;
	$end = $nb;
	$directory = false;
}
else
{
	$prevpos = pow(16,floor($node + 1));

	if($directory === true)
		$end = 16;
	else
		$end = $pos + $prevpos;

	if($pos > $nb || ($pos % 16) !== 0)
	{
		$beg = 0;
		$end = $directory === true ? 16 : $prevpos;
	}
	else
		$beg = $pos;
}

$cnt = pow(16,floor($node));

xivo::load_class('xivo::sort');
$sort = new xivo_sort(array('key' => 'identity'));
usort($rs,array(&$sort,'str_usort'));

if($directory === true)
{
	$_HTML->set_var('list',array_slice($rs,$beg,16));
	$_HTML->set_var('act','directory');
}
else
{
	$res = array();

	for($i = $beg,$j = $beg + $cnt - 1;$i < $end && $i < $nb;$i += $cnt,$j = $i + $cnt - 1)
	{
		if(isset($rs[$j]) === true)
			$res[] = array($rs[$i],$rs[$j],$i);
		else
		{
			$res[] = array($rs[$i],end($rs),$i);
			break;
		}
	}

	$_HTML->set_var('list',$res);
	$_HTML->set_var('act','menu');
}

$_HTML->set_var('node',$node);
$_HTML->set_var('maxnode',$maxnode);
$_HTML->set_var('pos',$beg);
$_HTML->set_var('prevpos',$prevpos);
$_HTML->set_var('name',$_QR['name']);
$_HTML->display($displaypath);
die();

?>
