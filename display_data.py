import argparse
import csv
import numpy as np
import matplotlib.pyplot as plt
from scipy import integrate

def find_local_min(value_list, min_val):
    """ Find minimum of values in range larger than min_val."""
    return min([val for val in value_list if val >= min_val])

parser = argparse.ArgumentParser(description='Script used to display SOC gauge Test Results')
parser.add_argument('csv_file', help='Choose data [.csv] to display', type=str)
args = parser.parse_args()


filename = args.csv_file
time, batt_volt, batt_curr, batt_soc, charger_volt, charger_curr = [],[],[],[],[],[]
with open(filename) as f:
    reader = csv.DictReader(f)

    for row in reader:
        time.append(float(row['time']))
        batt_volt.append(float(row['batt_voltage']))
        batt_curr.append(float(row['batt_current'])/1000.0)
        batt_soc.append(float(row['batt_soc']))
        charger_volt.append(float(row['charger_voltage']))
        charger_curr.append(float(row['charger_current']))

    # Convert data to numpy arrays
    # time = np.array(time)
    # batt_volt = np.array(batt_volt)
    # batt_curr = np.array(batt_curr)
    # batt_soc = np.array(batt_soc)
    # charger_volt = np.array(charger_volt)
    # charger_curr = np.array(charger_curr)

    # Start data where 100% SOC was reached
    window_l = min([i for i,v in enumerate(batt_soc) if v >= 100.0])
    window_r = len(time)
    print(window_l, window_r)
    time = time[window_l:window_r]
    batt_volt = batt_volt[window_l:window_r]
    batt_curr = batt_curr[window_l:window_r]
    batt_soc = batt_soc[window_l:window_r]
    charger_volt = charger_volt[window_l:window_r]
    charger_curr = charger_curr[window_l:window_r]

    qmax_as = 38.0 * 3600 # Estimated Capacity on H2P battery
    q = integrate.cumtrapz(batt_curr, time, initial=0)
    soc_calc = 100*(1-(qmax_as - q) / qmax_as) + 100

    #ylim_min = find_local_min(batt_soc, 50.0)
    ylim_min = min(batt_soc)

    fig, axs = plt.subplots(3, 1)
    axs[0].plot(time,batt_volt)
    axs[1].plot(time,batt_curr)
    axs[2].plot(time,batt_soc)
    axs[2].plot(time,soc_calc+0.5)
    axs[2].plot(time,soc_calc-0.5)
    axs[2].set_ylim([ylim_min-5, 105])

    plt.show()
