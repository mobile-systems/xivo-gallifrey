/*
 * XiVO Web-Interface
 * Copyright (C) 2006, 2007, 2008  Proformatique <technique@proformatique.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

var xivo_fm_ast_faxdetectenable = new Array();

xivo_fm_ast_faxdetectenable['it-incall-faxdetecttimeout'] = new Array();
xivo_fm_ast_faxdetectenable['it-incall-faxdetecttimeout']['property'] = new Array(
								{disabled: true, className: 'it-disabled'},
								{disabled: false, className: 'it-enabled'});
xivo_fm_ast_faxdetectenable['it-incall-faxdetecttimeout']['link'] = 'it-incall-faxdetectemail';

xivo_fm_ast_faxdetectenable['it-incall-faxdetectemail'] = new Array();
xivo_fm_ast_faxdetectenable['it-incall-faxdetectemail']['property'] = new Array(
								{readOnly: true, className: 'it-readonly'},
								{readOnly: false, className: 'it-enabled'});

xivo_attrib_register('fm_ast_faxdetectenable',xivo_fm_ast_faxdetectenable);

function xivo_ast_enable_faxdetect()
{
	if((faxdetectenable = xivo_eid('it-incall-faxdetectenable')) === false)
		return(false);
	else if((dialaction_answer_actiontype = xivo_eid('it-dialaction-answer-actiontype')) === false
	|| (dialaction_answer_application_action = xivo_eid('it-dialaction-answer-application-action')) === false
	|| dialaction_answer_actiontype.value !== 'application'
	|| dialaction_answer_application_action.value !== 'faxtomail')
	{
		enable = faxdetectenable.checked;
		faxdetectenable.disabled = false;
	}
	else
	{
		enable = false;
		faxdetectenable.disabled = true;
	}

	xivo_chg_attrib('fm_ast_faxdetectenable','it-incall-faxdetecttimeout',Number(enable));

	return(true);
}

function xivo_ast_incall_chg_dialaction_answer(obj)
{
	xivo_ast_chg_dialaction('answer',obj);
	xivo_ast_enable_faxdetect();
}

function xivo_ast_incall_chg_dialaction_actionarg_answer_application()
{
	xivo_ast_chg_dialaction_actionarg('answer','application');
	xivo_ast_enable_faxdetect();
}

function xivo_ast_incall_onload()
{
	xivo_ast_build_dialaction_array('answer');
	xivo_ast_dialaction_onload();

	xivo_ast_enable_faxdetect();
}

xivo_winload.push('xivo_ast_incall_onload();');
