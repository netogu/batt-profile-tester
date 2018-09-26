import argparse
import time
import six
import pyvisa as pyvisa

import nixnet
from nixnet import constants
from nixnet import types
from nixnet import convert

import os
import signal
import sys
from threading import Timer
from datetime import datetime
import csv
from batt_test_profile_loader import profile_state_machine

class battery:
    voltage = 0
    current = 0
    soc = 0
    temp = 0
    cell_volts = [0,0,0,0]
    data = []
    def __init__(self, name):
        self.name = name
    def pack_data(self, voltage, current, soc):
        self.voltage = voltage
        self.current = current
        self.soc = soc

    def list_data(self):
        return [self.voltage, self.current, self.soc]

class psu:

    voltage = 0
    current = 0
    voltage_setpoint = 0

    def __init__(self, name, visa_resource):
        self.name = name
        self.visa = visa_resource


    def pack_data(self, voltage, current):
        self.voltage = voltage
        self.current = current


    def list_data(self):
        return [self.voltage, self.current]


    def idn(self):
        return self.visa.query('*IDN?')


    def init(self):
        self.visa.write('OUTPUT OFF')
        self.visa.write('CURR:LIM 0')
        self.visa.write('CURR:LIM:NEG 0')
        self.visa.write('VOLT 0')


    def set_curr_lim(self, pos_lim, neg_lim):
        self.visa.write('CURR:LIM {}'.format(pos_lim))
        self.visa.write('CURR:LIM:NEG {}'.format(neg_lim))


    def set_voltage(self, volt):
        self.visa.write('VOLT {}'.format(volt))


    def set_output(self, state):
        if(state == 'ON'):
            self.visa.write('OUTPUT ON')
        elif(state == 'OFF'):
            self.visa.write('OUTPUT OFF')

    def set_charger_setpoints(self,voltage=0,ilim_pos=0, ilim_neg=0, output_state='OFF'):
        self.set_voltage(voltage)
        self.set_curr_lim(ilim_pos, ilim_neg)
        self.set_output(output_state)


    def read_data(self):
        self.voltage = float(self.visa.query('MEAS:VOLT?'))
        self.current = float(self.visa.query('MEAS:CURR?'))

class InfiniteTimer():
    """A Timer class that does not stop, unless you want it to."""

    def __init__(self, seconds, target):
        self._should_continue = False
        self.is_running = False
        self.seconds = seconds
        self.target = target
        self.thread = None


    def _handle_target(self):
        self.is_running = True
        self.target()
        self.is_running = False
        self._start_timer()

    def _start_timer(self):
        if self._should_continue: # Code could have been running when cancel was called.
            self.thread = Timer(self.seconds, self._handle_target)
            self.thread.start()

    def start(self):
        if not self._should_continue and not self.is_running:
            self._should_continue = True
            self._start_timer()
        else:
            print("Timer already started or running, please wait if you're restarting.")

    def cancel(self):
        if self.thread is not None:
            self._should_continue = False # Just in case thread is running and cancel fails.
            self.thread.cancel()
        else:
            print("Timer never started or failed to initialize.")

# Global Variables
interface = 'LIN1'
database = 'a123_h2p_database'
cluster = 'LISB'
frames = ['LISB_Frm2_AR', 'LISB_Frm4_AR']
signals = ['LISB_PackVolt', 'LISB_Bat_Curr', 'LISB_SOC_Absolute']
DISPLAY_RATE = 1 # every 1 second
SAMPLE_RATE = 0.2 # every 200ms


# Create Objects
batt = battery('A123_H2P')
charger = psu('Keysight', None)
today = datetime.now().timetuple()


# Functions
def display_data_task():
    """Display latest data on console."""
    print('Charger Voltage = {:2.2f}V | Charger Current = {:2.2f}A | Batt. Voltage = {:2.2f}V | Batt. Current = {:2.2f}mA | Batt. SOC = {:2.2f}'.format(*(charger.list_data() + batt.list_data())))
    #print('Charger Voltage = {}V / Charger Current = {}A'.format(*charger.list_data()))


def log_data():
    """Log line of data in session's .csv file."""


def main():

    parser = argparse.ArgumentParser(description='Script used to test SOC gauge performance')
    #parser.add_argument('pos_current_lim', help="Choose the charger's positive current limit", type=float)
    ##parser.add_argument('neg_curr_lim', help="Choose the charger's negative current limit", type=float)
    #parser.add_argument('voltage_high', help='Choose what the high level charger voltage is', type=float)
    #parser.add_argument('voltage_low', help='Choose what the low level charger voltage is', type=float)
    parser.add_argument('profile_file', help='Choose Test profile .csv file', type=str)
    parser.add_argument('test_name', help='Choose name of the test', type=str)
    parser.add_argument('charger_visa_name', help='Type in the charger VISA alias',type=str)

    args = parser.parse_args()
    print('Profile chosen : {}'.format(args.profile_file))



    # Open Charger VISA open_resource
    rm = pyvisa.ResourceManager()
    charger_visa = rm.open_resource(args.charger_visa_name)
    # Open log file
    filename = args.test_name + '_' + str(today[1]) + '_' + str(today[2]) + '_' + str(today[3]) + str(today[4]) + '.csv'
    print("Opening log file as {}".format(filename))
    log_file = open(filename,'w')
    header = "time,batt_voltage,batt_current,batt_soc,charger_voltage,charger_current\n"
    log_file.write(header)

    charger.visa = charger_visa
    print(charger.idn())
    charger.init()

    # Set up Profile State Machine
    local_path =  os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(local_path, args.profile_file)

    with open(filename) as profile:
        test_profile = profile_state_machine(profile)
        test_profile.set_event_function(charger.set_charger_setpoints)


        # Setup LIN Sessions
        with nixnet.FrameInSinglePointSession(interface, database, cluster, frames) as session:
            with convert.SignalConversionSinglePointSession(database, cluster, signals) as converter:

                session.intf.lin_term = constants.LinTerm.ON
                session.intf.lin_master = True

                def read_data_task():
                    """Aquires and Converts Telemetry data on the SCPI and LIN buses."""
                    # Read Telemetry
                    charger.read_data()
                    frame = session.frames.read(frame_type=types.LinFrame)

                    # Format Data
                    converted_signals = converter.convert_frames_to_signals(frame)
                    batt.pack_data(*[float(v) for (_, v) in converted_signals])

                # Set the schedule. This will also automatically enable master mode.
                session.start()
                session.change_lin_schedule(3)
                time.sleep(1)

                # Setup charger
                # charger.set_curr_lim(0, 0)
                # charger.set_voltage(0)
                # charger.set_output('OFF')


                display_task = InfiniteTimer(DISPLAY_RATE, display_data_task)
                #daq_task = InfiniteTimer(SAMPLE_RATE, read_data_task)

                def exit_signal_handler(signal, frame):
                    print('Shutting Down...')
                    charger.set_output('OFF')
                    display_task.cancel()
                    #daq_task.cancel()
                    sys.exit()
                signal.signal(signal.SIGINT, exit_signal_handler)

                display_task.start()
                #daq_task.start()

                loop_count = 0;
                start_time = time.time()
                next_step = 0


                while(1):
                    loop_start = time.time()
                    sample_time = loop_start - start_time
                    read_data_task()


                    # Logging data
                    data_row = "{},{},{},{},{},{}\n".format(sample_time, batt.voltage, batt.current, batt.soc, charger.voltage, charger.current)
                    log_file.write(data_row)

                    #Feed profile state machine
                    test_profile.run_profile(batt)
                    if(test_profile.done):
                        print('Profile ended.')
                        print('Data acquisition stopped.')
                        log_file.close()
                        print('Shutting Down...')
                        charger.set_output('OFF')
                        display_task.cancel()
                        sys.exit()

                    loop_time = time.time() - loop_start
                    loop_wait = loop_time - SAMPLE_RATE
                    if(loop_wait < 0):
                        loop_wait = 0
                    time.sleep(loop_wait)

    print('Data acquisition stopped.')


if __name__ == '__main__':
    main()
