import time
import sys
import signal
from threading import Timer
import nixnet
from nixnet import constants
from nixnet import types
from nixnet import convert

ibs_name = 'IBS_GEN2'


if ibs_name == 'IBS_GEN1':
    # GEN1
    #Global Variables
    interface = 'LIN2'
    database = 'hella_gen1_ibs'
    cluster = 'Cluster'
    frames = ['IBS_FRM2','IBS_FRM5','IBS_FRM6']
    signals = [
                'BatteryVoltage',
                'BatteryCurrent',
                'BatteryTemperature',
                'StateOfCharge',
                'NominalCapacity',
                'Recalibrated'
                ]
    lin_schedule = 0
else:
    # GEN2 IBS
    interface = 'LIN2'
    database = 'hella_gen2_ibs'
    cluster = 'Cluster'
    frames = ['IBS_UIT','IBS_BZE1','IBS_BZE2']
    signals = [
                'BatteryVoltage',
                'BatteryCurrent',
                'BatteryTemperature',
                'StateOfCharge',
                'NominalCapacity',
                'Recalibrated'
                ]
    lin_schedule = 1

DISPLAY_RATE = 1 # every 1 second
SAMPLE_RATE = 1 # every 200ms

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

class battery:
    voltage = 0
    current = 0
    soc = 0
    temp = 0
    cell_volts = [0,0,0,0]
    data = []
    def __init__(self, name):
        self.name = name
    def pack_data(self, voltage, current, temp, soc, soc_nom, soc_recalibrated):
        self.voltage = voltage
        self.current = current
        self.temp = temp
        self.soc = soc
        self.soc_nom = soc_nom
        self.soc_recalibrated = soc_recalibrated

    def list_data(self):
        return [self.voltage, self.current, self.temp, self.soc, self.soc_nom, self.soc_recalibrated]



def main():

    batt = battery('YUASA_30')

    def display_data_task():
        """Display latest data on console."""
        print('Batt. Voltage = {:2.2f}V | Batt. Current = {:2.4f}A | Batt. temp = {:2.2f}C | Batt. SOC = {:2.2f}% | Q.Nom = {:2.2f}Ah | SOC.Recal = {}'.format(*( batt.list_data())))
    # Setup LIN Sessions
    with nixnet.FrameInSinglePointSession(interface, database, cluster, frames) as session:
        with convert.SignalConversionSinglePointSession(database, cluster, signals) as converter:

            session.intf.lin_term = constants.LinTerm.ON
            session.intf.lin_master = True

            def read_data_task():
                """Aquires and Converts Telemetry data on the SCPI and LIN buses."""
                # Read Telemetry
                frame = session.frames.read(frame_type=types.LinFrame)

                # Format Data
                converted_signals = converter.convert_frames_to_signals(frame)
                batt.pack_data(*[float(v) for (_, v) in converted_signals])

            # Set the schedule. This will also automatically enable master mode.
            session.start()

            session.change_lin_schedule(lin_schedule)
            time.sleep(1)



            display_task = InfiniteTimer(DISPLAY_RATE, display_data_task)


            def exit_signal_handler(signal, frame):
                print('Shutting Down...')
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
                # status = session.num_unused
                # print(status)
                loop_time = time.time() - loop_start
                loop_wait = SAMPLE_RATE - loop_time
                if(loop_wait < 0):
                    loop_wait = 0
                time.sleep(loop_wait)

    print('Data acquisition stopped.')


if __name__ == '__main__':
    main()
