#!/usr/bin/python
# vim: set expandtab:

# Copyright: (c) 2018, David Beveridge <dave@bevhost.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: pfsense_group

short_description: Creates a usergroup

description: Creates a group usable by LDAP or Local Auth etc

version_added: "2.7"

options:
  name: group name
    required: true
  description:
    required: false
  scope:
    default: remote
    required: false
  priv:
    description: Privileges assigned to users in this group
    required: true
    possible values:
        see example below; or create a group in the GUI and export it 
        or look at the config diff in diagnostics/backup & restore/config history
author:
    - David Beveridge (@bevhost)

notes:
Ansible is located in an different place on BSD systems such as pfsense.
You can create a symlink to the usual location like this

ansible -m raw -a "/bin/ln -s /usr/local/bin/python2.7 /usr/bin/python" -k -u root mybsdhost1

Alternatively, you could use an inventory variable

[fpsense:vars]
ansible_python_interpreter=/usr/local/bin/python2.7

'''

EXAMPLES = '''
- name: Create Group
  pfsense_group:
   name: Staff
   description: Internal Staff Users
   priv:
#    - page-all
    - page-help-all
    - page-dashboard-all
    - page-dashboard-widgets
#    - user-shell-access

'''

RETURN = '''
group:
    description: dict containing all user groups
debug:
    description: Any debug messages for unexpected input types
    type: str
phpcode:
    description: Actual PHP Code sent to pfSense PHP Shell
'''

from ansible.module_utils.basic import AnsibleModule
import json
import platform
import os

cmd = "/usr/local/sbin/pfSsh.php"

def write_config(module,configuration):

    php = configuration+'\nwrite_config();\nexec\nexit\n'

    rc, out, err = module.run_command(cmd,data=php)
    if rc != 0:
        module.fail_json(msg='error writing config',error=err, output=out)


def read_config(module,section):

    php = 'echo "\n".json_encode($config["'+section+'"])."\n";\nexec\nexit\n'

    rc, out, err = module.run_command(cmd,data=php)
    if rc != 0:
        module.fail_json(msg='error reading config',error=err, output=out)

    start = "\npfSense shell: exec\n"
    end = "\npfSense shell: exit\n"
    try:
        s = out.index(start) + len(start)
        e = out.index(end)
        return json.loads(out[s:e])
    except:
        module.fail_json(msg='error converting to JSON', json=out[s:e])


def search(elements,key,val):

    if type(elements) in [dict,list]:
        for k,v in enumerate(elements):
            if v[key] == val:
                return k
    return ""


def run_module():

    module_args = dict(
        name=dict(required=True, default=None),
        scope=dict(required=False, default='remote', choices=['local','remote']),
        description=dict(required=False, default=''),
        priv=dict(required=True, type=list),
        state=dict(required=False, default='present', choices=['present', 'absent'])
    )

    result = dict(
        changed=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    params = module.params
    priv = params['priv']

    configuration = ""

    # Make sure we're actually targeting a pfSense firewall
    if not os.path.isfile(cmd):
        module.fail_json(msg='pfSense shell not found at '+cmd)
    if platform.system() != "FreeBSD":
        module.fail_json(msg='pfSense platform expected: FreeBSD found: '+platform.system())

    system = read_config(module,'system')
    index = search(system['group'],'name',params['name'])
    if index=='':
        gid = system['nextgid']
        configuration += "$config['system']['nextgid']++;\n"
    else:
        gid = system['group'][index]['gid']

    base = "$config['system']['group'][" + str(index) + "]"
    if params['state'] == 'present':
        for p in ['name','description','scope']:
            if type(params[p]) in [str,unicode]:
                if index=='':
                    configuration += "$group['"+p+"']='" + params[p] + "';\n"
                elif system['group'][index][p] != params[p]:
                    configuration += base + "['"+p+"']='" + params[p] + "';\n"
        if index=='':
            configuration += "$group['gid']='" + gid + "';\n"
            configuration += "$group['priv']=['"+"','".join(priv)+"'];\n"
            configuration += base + "=$group;\n"
        elif set(system['group'][index]['priv']) != set(priv):
            configuration += base + "['priv']=['"+"','".join(priv)+"'];\n"

    elif params['state'] == 'absent':
        if index != '':
            configuration += "unset("+base+");\n"
    else:
        module.fail_json(msg='Incorrect state value, possible choices: absent, present(default)')

    result['phpcode'] = configuration

    if module.check_mode:
        module.exit_json(**result)

    if configuration != '':
        write_config(module,configuration)
        result['changed'] = True

    cfg = read_config(module,'system')
    result['group'] = cfg['group']

    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()




