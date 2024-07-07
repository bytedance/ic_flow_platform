# IC Flow Platform V1.3 (2024.07.15)

## Update history
***
|Version |Date            | Update content      |
| :-----------| :-----------| :-----------------  |
| V1.3   |(2024.07.15)    | Brand new user configuration interface and API function to support customized daily work scenarios |
| V1.2   |(2023.12.31)    | Support more complex logic control and centrally manage user settings |
| V1.1.1 |(2023.08.31)    | Optimize menu bar functions and interface operations |
| V1.1   |(2023.07.14)    | Fix some operation bugs and optimize CONFIG TAB operation mode |
| V1.0   |(2023.02.02)    | Open source and the first official version is released |


## Introduction
***

### 0. What is IFP?

IFP (ic flow platform) is an integrated circuit design
flow platform, mainly used for IC process specification
 management and data flow control.


### 1. Python dependency
Need python3.8.8, Anaconda3-2021.05-Linux-x86_64.sh is better.
Install python library dependency with command

    pip install -r requirements.txt


### 2. Install
Copy install package into install directory.
Execute below command under install directory.

    python3 install.py


### 3. Administrator configs default settings for user
  - ${IFP_INSTALL_PATH}/config/config.py : default system configuration
  - ${IFP_INSTALL_PATH}/config/default.yaml : default flow/task and corresponding action attribute (Main flow, can be distinguished by project and user group)
  - ${IFP_INSTALL_PATH}/config/api.yaml : default API setting (Customized functions to support daily work and can be distinguished by project and user group too)
  - ${IFP_INSTALL_PATH}/config/env.* : default user environment setting

### 4. Demo case
IFP will enter demo mode when you set ${IFP_DEMO_MODE}=TRUE, such as (bash env):

    export IFP_DEMO_MODE=TRUE

<img src="./data/pictures/readme/IFP_demo.png" width="80%">

### 5. Run IFP

  - Step 1 : Create working path and enter into the directory
  - Step 2 : Execute ${IFP_INSTALL_PATH}/bin/ifp to run IFP with GUI mode
  - Step 3 : Enter `Project_name` and `User_group` in `CONFIG-Setting interface` to match admin's default flow setting and API setting

<img src="./data/pictures/readme/IFP_setting.png" width="80%">

  - Step 4 : Create your tasks in `CONFIG-Task interface` and adjust task detailed settings

<img src="./data/pictures/readme/IFP_set_task.png" width="80%">

  - Step 5 : Adjust task actuating logic in `CONFIG-Dependency interface`, if you select `Enable user dependency interface`

<img src="./data/pictures/readme/IFP_set_dependency.png" width="80%">

  - Step 6 : Adjust IFP internal variables in `CONFIG-Variable interface`, if you select `Enable user variable interface`

<img src="./data/pictures/readme/IFP_set_variable.png" width="80%">

  - Step 7 : Enable/Disable API functions in `CONFIG-API interface`, if you select `Enable user API interface`

<img src="./data/pictures/readme/IFP_set_API.png" width="80%">

  - Step 8 : Execute actions and monitor the progress in `MAIN interface`

<img src="./data/pictures/readme/IFP_main_tab.png" width="80%">


More details please see ["docs/IFP_user_manual.pdf"](./docs/IFP_user_manual.pdf) and ["docs/IFP_admin_manual.pdf"](./docs/IFP_admin_manual.pdf)
