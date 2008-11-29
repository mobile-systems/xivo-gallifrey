<?php

require_once(xivo_file::joinpath(XIVO_PATH_LIB,'datastorage','helper','table.inc'));

class xivo_accesswebservice_abstract_sql extends xivo_datastorage_helper_table
{
	var $_table	= 'accesswebservice';
	var $_primary	= array('id' => 0);
	var $_disable	= 'disable';
	var $_unique	= 'name';

	function xivo_accesswebservice_abstract_sql(&$dso,$param=array())
	{
		parent::_init(&$dso,$param);
	}

	function get($id,$disable=null)
	{
		if(($r = parent::get($id,$disable)) === false)
			return(false);

		$r['obj'] = xivo_unserialize($r['obj']);

		return($r);
	}

	function acl_edit($id,$arr)
	{
		if(($obj = $this->_get_obj($id)) === false)
			return(false);

		$obj['acl'] = $arr;

		return($this->_save_obj($id,$obj));
	}

	function _save_obj($id,$obj)
	{
		if(($id = xivo_ulongint($id)) === 0 || is_array($obj) === false)
			return(false);

		return($this->_dso->update($this->_table,
					   array('obj' => serialize($obj)),
					   array('id' => $id)));
	}

	function _get_obj($id)
	{
		if(($id = xivo_ulongint($id)) === 0)
			return(false);

		$this->_dso->new_select($this->_table,'obj');
		$this->_dso->where(array('id' => $id));

		if(($r = $this->_dso->select_one()) === false)
			return(false);

		return(xivo_unserialize($r));
	}
}

?>