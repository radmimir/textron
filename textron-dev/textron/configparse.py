import configparser
import os
from shutil import copyfile
from sys import argv

from textron.logging_module import write_to_log

# if (not '--verbose' in argv) and (not '-v' in argv):
#     print = write_to_log
print = write_to_log

def create_config(path):
    """
    Create a config file
    """
    # import pdb; pdb.set_trace()
    config = configparser.ConfigParser()
    config['Settings'] = {
        'debug_profiles_dir' : 'C:/Roima/TBM_9_5_2018/TBM_9_5_2018/Profiles/1/',
        'calibration_arrays' : 'calibration_arrays.csv'
        }
    config['Calibration'] = {
        'cv_shift_x': '0.3',
        'cc_shift_x': '15.07',
        'cv_shift_y': '-0.06',
        'cc_shift_y': '-0.09',
        'cv_tilt_a': '-0.02',
        'cc_tilt_a': '0.00',
        'cv_tilt_b': '-0.02',
        'cc_tilt_b': '-0.2',
        'startSection': '150',
        'endSection': '300'
        }
    config['Processing'] = {
        'bestfit_method': 'default',
        'points_cut_right': '18',
        'min_stock_initial_check': '-0.08',
        'points_for_initial_check': '6',
        'C2_check': 'True'
        }
    config['Grinding'] = {
        'no_stock_grinder': '1',
        'no_stock_threshold': '0.1'}
    config['Profile'] = {
        'control_sections': '12.1, 22.1, 32.1, 34.1',
        'alpha': '-0.45, 6.28, 16.45, 18.46',
        'gamma2': '49.22, 51.57, 58.04, 59.44',
        'b2': '7.31, 7.01, 6.45, 6.33',
        'C2': '0.51, 0.44, 0.40, 0.38',
        'C2Tol': '0.12',
        'Y2': '2.942, 3.402, 3.913, 4.019',
        'R2': '0.15, 0.156, 0.157, 0.150',
        'C2Dist': '1'
        }
    with open(path, "w") as config_file:
        config.write(config_file)

def delete_setting(path, section, setting):
    """
    Delete a setting
    """
    config = get_config(path)
    config.remove_option(section, setting)
    with open(path, "w") as config_file:
        config.write(config_file)

def get_config(path):
    """
    Returns the config object
    """
    if not os.path.exists(path):
        try:
            copyfile('settings.ini.default', 'settings.ini')
        except:
            create_config(path)
        else:
            print('Could not find config file. New one created.')

    config = configparser.ConfigParser(comment_prefixes = '/',
        allow_no_value = True)
    config.read(path, encoding = 'utf-8')
    return config

def get_setting(path, section, setting):
    """
    Print out a setting
    """
    config = get_config(path)
    value = config[section][setting]
    return value

def update_setting(path, section, setting, value):
    """
    Update a setting
    """
    config = get_config(path)
    config[section][setting] = value
    with open(path, "w", encoding = 'utf-8') as config_file:
        config.write(config_file)

if __name__ == "__main__":
#    path = "settings.ini"
#    font = get_setting(path, 'Settings', 'font')
#    font_size = get_setting(path, 'Settings', 'font_size')
#
#    update_setting(path, "Settings", "font_size", "12")
#    delete_setting(path, "Settings", "font_style")
    pass
