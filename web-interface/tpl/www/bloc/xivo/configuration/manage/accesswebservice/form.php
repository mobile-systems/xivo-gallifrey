<?php

$form = &$this->get_module('form');

$info = $this->get_var('info');
$element = $this->get_var('element');

echo	$form->text(array('desc'	=> $this->bbf('fm_name'),
			  'name'	=> 'name',
			  'labelid'	=> 'name',
			  'size'	=> 15,
			  'default'	=> $element['name']['default'],
			  'value'	=> $info['name'])),

	$form->text(array('desc'	=> $this->bbf('fm_login'),
			  'name'	=> 'login',
			  'labelid'	=> 'login',
			  'size'	=> 15,
			  'default'	=> $element['login']['default'],
			  'value'	=> $info['login'])),

	$form->text(array('desc'	=> $this->bbf('fm_passwd'),
			  'name'	=> 'passwd',
			  'labelid'	=> 'passwd',
			  'size'	=> 15,
			  'default'	=> $element['passwd']['default'],
			  'value'	=> $info['passwd'])),

	$form->text(array('desc'	=> $this->bbf('fm_host'),
			  'name'	=> 'host',
			  'labelid'	=> 'host',
			  'size'	=> 15,
			  'default'	=> $element['host']['default'],
			  'value'	=> $info['host']));
?>
<div class="fm-field fm-description">
	<p>
		<label id="lb-description" for="it-description"><?=$this->bbf('fm_description');?></label>
	</p>
	<?=$form->textarea(array('field'	=> false,
				 'label'	=> false,
				 'name'		=> 'description',
				 'id'		=> 'it-description',
				 'cols'		=> 60,
				 'rows'		=> 5,
				 'default'	=> $element['description']['default']),
			   $info['description']);?>
</div>