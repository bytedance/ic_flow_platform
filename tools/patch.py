# -*- coding: utf-8 -*-
import os
import re
import sys
import shutil
import filecmp
import argparse

sys.path.append(str(os.environ['IFP_INSTALL_PATH']) + '/common')
import common

os.environ['PYTHONUNBUFFERED'] = '1'


def read_args():
    """
    Read in arguments.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-p', '--patch_path',
                        default='',
                        help='Specify patch path (new install package path).')

    args = parser.parse_args()

    if not os.path.exists(args.patch_path):
        common.bprint('"' + str(args.path_path) + '": No such patch path.', level='Error')
        sys.exit(1)

    return args.patch_path


class Patch:
    def __init__(self, patch_path):
        self.install_path = os.path.realpath(os.environ['IFP_INSTALL_PATH'])
        self.patch_path = os.path.realpath(patch_path)
        self.ignore_py_list = ['config/config.py']

        print('Install Path : ' + str(self.install_path))
        print('Patch   path : ' + str(self.patch_path))
        print('')

        self.check_path_name()

    def check_path_name(self):
        """
        Make sure install_path and the patch_path have the same directory name.
        """
        if os.path.basename(self.install_path) != os.path.basename(self.patch_path):
            common.bprint('Current install path name is "' + str(os.path.basename(self.install_path)) + '", but patch path name is "' + str(os.path.basename(self.patch_path)) + '".', level='Warning')

            choice = input('Do you want to continue? (y|n) ')

            if (choice == 'n') or (choice == 'N') or (choice == 'no'):
                os.sys.exit(0)
            else:
                print('')

    def get_py_list(self, specified_path):
        """
        Get all python files from specified_path with relative path format.
        """
        py_list = []

        for root_path, c_dirs, c_files in os.walk(specified_path):
            for c_file in c_files:
                if re.match(r'^.*\.py$', c_file) and os.path.isfile(str(root_path) + '/' + str(c_file)):
                    if root_path == specified_path:
                        py_file = c_file
                    else:
                        relative_path = re.sub(str(specified_path) + '/', '', root_path)
                        py_file = str(relative_path) + '/' + str(c_file)

                    py_list.append(py_file)

        return py_list

    def run(self):
        """
        Compare python files with self.install_path and self.patch_path.
        Copy new files into self.install_path.
        copy updated files into self.install_path.
        """
        install_py_list = self.get_py_list(self.install_path)
        patch_py_list = self.get_py_list(self.patch_path)

        for py_file in patch_py_list:
            if py_file not in self.ignore_py_list:
                abs_install_py = str(self.install_path) + '/' + str(py_file)
                abs_patch_py = str(self.patch_path) + '/' + str(py_file)

                if (py_file not in install_py_list) or (not filecmp.cmp(abs_install_py, abs_patch_py)):
                    # Remove old python file.
                    if py_file in install_py_list:
                        print('> Remove old python file "' + str(abs_install_py) + '".')

                        try:
                            os.remove(abs_install_py)
                        except Exception as error:
                            common.bprint('Failed on removing old python file "' + str(abs_install_py) + '".', level='Error')
                            common.bprint(error, color='red', display_method=1, indent=9)
                            sys.exit(1)

                    # Create directory for new python file.
                    abs_install_path = os.path.dirname(abs_install_py)

                    if not os.path.exists(abs_install_path):
                        print('> Create directory "' + str(abs_install_path) + '".')

                        try:
                            os.makedirs(abs_install_path)
                        except Exception as error:
                            common.bprint('Failed on creating directory "' + str(abs_install_path) + '".', level='Error')
                            common.bprint(error, color='red', display_method=1, indent=9)
                            sys.exit(1)

                    # Copy path python file into install path.
                    print('> Copy python file "' + str(abs_patch_py) + '" into "' + str(abs_install_py) + '".')

                    try:
                        shutil.copyfile(abs_patch_py, abs_install_py)
                    except Exception as error:
                        common.bprint('Failed on copying file "' + str(abs_patch_py) + '" into "' + str(abs_install_py) + '".', level='Error')
                        common.bprint(error, color='red', display_method=1, indent=9)
                        sys.exit(1)


################
# Main Process #
################
def main():
    (patch_path) = read_args()
    my_patch = Patch(patch_path)
    my_patch.run()


if __name__ == '__main__':
    main()
