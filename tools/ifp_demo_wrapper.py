import argparse
import os
import sys
import yaml
from collections import OrderedDict


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--project',
                        default='demo',
                        help='Project name (default: demo)')
    parser.add_argument('-g', '--group',
                        default='syn',
                        help='Group name (default: syn)')
    parser.add_argument('-b', '--blocks',
                        nargs='+',
                        choices=['bit_slice', 'bit_top'],
                        required=True,
                        help='Block name(s): choose one or both of [bit_slice, bit_top]')
    parser.add_argument('-v', '--version',
                        default='v1.4.2',
                        help='Version name, e.g., v1.4.2')
    parser.add_argument('-o', '--output',
                        default='ifp.cfg.yaml',
                        help='Output filename (default: ifp.cfg.yaml)')

    args = parser.parse_args()

    return args


def represent_ordereddict(dumper, data):
    return dumper.represent_dict(data.items())


yaml.add_representer(OrderedDict, represent_ordereddict)


def generate_config(project, group, blocks, version, output):
    ifp_install_path = os.environ.get('IFP_INSTALL_PATH')

    if ifp_install_path is None:
        print("Error: IFP_INSTALL_PATH environment variable is not set.")
        sys.exit(1)

    default_yaml_file = f"{ifp_install_path}/config/default.{project}.{group}.yaml"

    if not os.path.exists(default_yaml_file):
        print(f"Error: Cannot find default YAML file: {default_yaml_file}", file=sys.stderr)
        sys.exit(1)

    with open(default_yaml_file, 'r') as f:
        default_data = yaml.safe_load(f)

    new_config = OrderedDict()
    new_config["VAR"] = OrderedDict([
        ("BSUB_QUEUE", "normal"),
        ("MAX_RUNNING_JOBS", "6")
    ])

    block_dict = OrderedDict()
    for block in blocks:
        block_dict[block] = {
            version: OrderedDict([
                ("syn", OrderedDict((task, {}) for task in default_data["FLOW"].get("syn", []))),
                ("fv", OrderedDict((task, {}) for task in default_data["FLOW"].get("fv", []))),
                ("sta", OrderedDict((task, {}) for task in default_data["FLOW"].get("sta", [])))
            ])
        }

    new_config["BLOCK"] = block_dict
    new_config["GROUP"] = group
    new_config["PROJECT"] = project
    new_config["API_YAML"] = f"{ifp_install_path}/config/api.{project}.{group}.yaml"
    new_config["DEFAULT_YAML"] = f"{ifp_install_path}/config/default.{project}.{group}.yaml"

    with open(output, 'w') as OF:
        yaml.dump(new_config, OF, default_flow_style=False, sort_keys=False)

    print(f'    *INFO*: Configuration file generated successfully: "{os.path.abspath(output)}"')


def main():
    args = read_args()
    generate_config(args.project, args.group, args.blocks, args.version, args.output)


if __name__ == "__main__":
    main()
