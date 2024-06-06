import csv
from io import StringIO
import sys
import yaml

xml_odoo = """<?xml version="1.0" encoding="utf-8" ?>
<odoo>{xml_content}

</odoo>
"""

xml_file_template = """

    <record id="file_template_{key}" model="cx.tower.file.template">
        <field name="module">{module}</field>
        <field name="name">{name}</field>
        <field name="file_name">{file_name}</field>
        <field name="server_dir">{server_dir}</field>
        <field
            name="tag_ids"
            eval="[(6, 0, [ref('{module}.tag_{module}')])]"
        />
        <field name="note">
{note}
        </field>
        <field name="code">
{code}
        </field>
    </record>"""

xml_command = """

    <record id="command_{key}" model="cx.tower.command">
        <field name="module">{module}</field>
        <field name="name">{name}</field>
        <field
            name="tag_ids"
            eval="[(6, 0, [ref('{module}.tag_{module}')])]"
        />
        <field name="code">
{code}
        </field>
    </record>"""

xml_plan = """

    <!-- FLIGHT PLAN: {name} -->
    <record id="plan_{key}" model="cx.tower.plan">
        <field name="module">{module}</field>
        <field name="name">{name}</field>
        <field
            name="tag_ids"
            eval="[(6, 0, [ref('{module}.tag_{module}')])]"
        />
        <field name="note">
{note}
        </field>
    </record>"""

xml_plan_line = """
    <!-- Line -->
    <record id="plan_{key}_line_{line_no}" model="cx.tower.plan.line">
        <field name="sequence">{line_no}</field>
        <field name="plan_id" ref="plan_{key}" />
        <field name="command_id" ref="{command}" />
        <field name="use_sudo">{use_sudo}</field>
    </record>"""

xml_plan_line_action = """
    <!-- Action -->
    <record id="plan_{key}_line_{line_no}_action_{action_no}" model="cx.tower.plan.line.action">
        <field name="line_id" ref="plan_{key}_line_{line_no}" />
        <field name="sequence">{action_no}</field>
        <field name="condition">{condition}</field>
        <field name="value_char">{value_char}</field>
        <field name="action">{action}</field>
    </record>"""

xml_server = """

    <!-- SERVER: {name} -->
    <record id="server_{key}" model="cx.tower.server">
        <field name="name">{name}</field>
        <field name="ssh_username">admin</field>
        <field name="ssh_password">admin</field>
        <field name="ip_v4_address">1.2.3.4</field>
    </record>"""

xml_server_variable_value = """
    <record id="server_{server_key}_{var_key}" model="cx.tower.variable.value">
        <field name="module">{module}</field>
        <field name="server_id" ref="server_{server_key}" />
        <field name="variable_id" ref="{full_var_key}" />
        <field name="value_char">{var_value}</field>
    </record>"""

xml_variable = """

    <record id="variable_{key}" model="cx.tower.variable">
        <field name="module">{module}</field>
        <field name="name">{key}</field>
    </record>"""

xml_global_variable_value = """
    <record id="global_value_{key}" model="cx.tower.variable.value">
        <field name="module">{module}</field>
        <field name="variable_id" ref="variable_{key}" />
        <field name="is_global">True</field>
        <field name="value_char">{global_value}</field>
    </record>"""

def file_templates_to_xml(yaml_data):
    xml_content = ""
    for key, tmpl in (
        yaml_data.get("file_templates") and yaml_data["file_templates"].items() or []
    ):
        # file template
        xml_content += xml_file_template.format(
            key=key,
            module=yaml_data["module"],
            name=tmpl["name"],
            file_name=tmpl["file_name"],
            server_dir=tmpl["server_dir"],
            note=tmpl.get("note", ""),
            code=tmpl["code"],
        )
    return _xml_odoo(xml_content)

def commands_to_xml(yaml_data):
    xml_content = ""
    for key, command in (
        yaml_data.get("commands") and yaml_data["commands"].items() or []
    ):
        # command
        xml_content += xml_command.format(
            key=key,
            module=yaml_data["module"],
            name=command["name"],
            code=command["code"],
        )
    return _xml_odoo(xml_content)

def plans_to_xml(yaml_data):
    xml_content = ""
    for key, plan in (yaml_data.get("plans") and yaml_data["plans"].items() or []):
        # flight plan
        xml_content += xml_plan.format(
            module=yaml_data["module"],
            key=key,
            name=plan["name"],
            note=plan.get("note", ""),
        )
        line_no = 0
        for line in plan["lines"]:
            # line
            line_no += 1
            xml_content += xml_plan_line.format(
                key=key,
                line_no=line_no,
                command=_build_xmlid(line, "command"),
                use_sudo=line["use_sudo"],
            )
            action_no = 0
            for action in line.get("actions") or []:
                # action
                action_no += 1
                xml_content += xml_plan_line_action.format(
                    key=key,
                    line_no=line_no,
                    action_no=action_no,
                    condition=action["condition"],
                    value_char=action["value_char"],
                    action=action["action"]
                )
    return _xml_odoo(xml_content)

def servers_to_xml(yaml_data):
    xml_content = ""
    if not yaml_data.get("servers"):
        return ""
    for key, server in yaml_data.get("servers") and yaml_data["servers"].items() or []:
        # server
        xml_content += xml_server.format(
            module=yaml_data["module"],
            key=key,
            name=key,
        )
        if server:
            for ambiguous_var_key, var_value in server["variables"].items():
                # server variable value
                var_key, full_var_key = _build_var_keys(ambiguous_var_key)
                xml_content += xml_server_variable_value.format(
                    module=yaml_data["module"],
                    server_key=key,
                    var_key=var_key,
                    full_var_key=full_var_key,
                    var_value=var_value,
                )
    return _xml_odoo(xml_content)

def variables_to_xml(yaml_data):
    xml_content = ""
    for key, global_value in (
        yaml_data.get("variables") and yaml_data["variables"].items() or []
    ):
        # variable
        xml_content += xml_variable.format(
            module=yaml_data["module"],
            key=key,
        )
        if global_value:
            # global variable value
            xml_content += xml_global_variable_value.format(
                module=yaml_data["module"],
                key=key,
                global_value=global_value,
            )
    return _xml_odoo(xml_content)

def _file_to_data(yaml_file):
    with open(yaml_file, 'r') as file:
        yaml_data = yaml.safe_load(file)
    return yaml_data

def _build_xmlid(yaml_data, keyword):
    module = yaml_data.get("module") or ""
    if module:
        module += "."
    xmlid = module + keyword + "_" + yaml_data[keyword]
    return xmlid

def _build_var_keys(ambiguous_var_key):
    if "." in ambiguous_var_key:
        module, var_key = ambiguous_var_key.split(".")
        return "variable_" + var_key, module + ".variable_" + var_key
    else:
        var_key = ambiguous_var_key
        return "variable_" + var_key, "variable_" + var_key

def _xml_odoo(xml_content):
    return xml_odoo.format(xml_content=xml_content)

convert = sys.argv[1]
yaml_file = sys.argv[2]
xml_file = sys.argv[3]

function_to_call = globals()[convert + "_to_xml"]
yaml_data = _file_to_data(yaml_file)
xml_string = function_to_call(yaml_data)
open(xml_file, 'w').write(xml_string)
