import time
import six
import sys
import signal
from threading import Timer
import nixnet
from nixnet import constants
from nixnet import types
from nixnet import convert
import struct


class IBS200_GEN1():
    """ Define IBS200 GEN1 Object."""

    def __init__(self, lin_interface, lin_database_name):
        self.interface = lin_interface
        self.database = lin_database_name
        self.cluster = 'Cluster'
        self.master_req_output_frames = ['MasterReq']
        self.slave_resp_input_frames =  ['SlaveResp']
        self.MasterReqId = 0x3C
        self.master_payloads = {
        'Empty_Frame': [0x00, 0x00, 0x00, 0x00 ,0x00, 0x00, 0x00, 0x00],
        'BattCap_Read':[0x01, 0x06, 0xB2, 0x39, 0xFF, 0x7F, 0xFF, 0xFF],
        'BattCap_Write':[0x01, 0x03, 0xB5, 0x39, 0xFF, 0xFF, 0xFF, 0xFF],
        'BattType_Read':[0x01, 0x06, 0xB2, 0x3A, 0xFF, 0x7F, 0xFF, 0xFF],
        'BattType_Write':[0x01, 0x03, 0xB5, 0x3A, 0x1E, 0xFF, 0xFF, 0xFF],
        'BattTable_State':[0x01, 0x01, 0x30, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],
        'BattTable_OnOff':[0x82, 0x06, 0x31, 0x00, 0x11, 0x22, 0x33, 0x44],
        'U0_MinMax_Read':[0x82, 0x06, 0xB2, 0x30, 0xFF, 0x7F, 0xFF, 0xFF],
        'U0_MinMax_Write':[0x82, 0x06, 0xB5, 0x30, 0xFF, 0x7F, 0xFF, 0xFF],
        'IQbatt_Read':[0x82, 0x06, 0xB2, 0x3C, 0xFF, 0x7F, 0xFF, 0xFF],
        'IQbatt_Write':[0x82, 0x04, 0xB5, 0x3C, 0xFF, 0x7F, 0xFF, 0xFF]}


    def set_switch_table_OnOff(self, state='Off'):
        """ Change Master Payload to match table OnOff state request."""

        if(state == 'On'):
            self.master_payloads['BattTable_OnOff'][3] = 1
        elif(state == 'Off'):
            self.master_payloads['BattTable_OnOff'][3] = 0
        else:
            print('Error : Wrong State entered')

    def set_nominal_capacity(self, capacity_ah=30):
        """ Set Nominal Capacity value in Master Req payload."""

        self.master_payloads['BattCap_Write'][4] = capacity_ah

    def set_u0_minmax(self, u0_min = None, u0_max = None,):
        """ Set U0 Min/Max Values in Master Req Payload in 1mV Resolution."""

        u0_min_low = (0x0FF & u0_min)
        u0_min_high = (0xFF00 & u0_min) >> 8
        u0_max_low = (0x0FF & u0_max)
        u0_max_high = (0xFF00 & u0_max) >> 8

        self.master_payloads['U0_MinMax_Write'][4] = u0_min_high
        self.master_payloads['U0_MinMax_Write'][5] = u0_min_low
        self.master_payloads['U0_MinMax_Write'][6] = u0_max_high
        self.master_payloads['U0_MinMax_Write'][7] = u0_max_low

    def set_ibatt_quiescent(self, iqbatt = None):
        """ Set battery quiescent current in Master Req payload."""

        self.master_payloads['IQbatt_Write'][4] = iqbatt








def exit_signal_handler(signal, frame):
    print('Shutting Down...')
    sys.exit()
signal.signal(signal.SIGINT, exit_signal_handler)

def main():

    ibs = IBS200_GEN1('LIN2', 'hella_gen1_ibs')

    # User Defined Configuration

    C_NOMINAL = 30 #Ah
    U0_MIN = 11000 #mV
    U0_MAX = 13000 #mV
    U0_TOL = 150 #mV
    IQBATT = 200 #mA(100mA Default)

    # Set Master payloads

    ibs.set_nominal_capacity(capacity_ah=C_NOMINAL)
    ibs.set_u0_minmax(u0_min = U0_MIN, u0_max = U0_MAX)
    ibs.set_ibatt_quiescent(iqbatt = IQBATT)



    # Setup LIN Sessions
    with nixnet.FrameInSinglePointSession(ibs.interface, ibs.database, ibs.cluster, ibs.slave_resp_input_frames) as input_session:
        with nixnet.FrameOutQueuedSession(ibs.interface, ibs.database, ibs.cluster, ibs.master_req_output_frames) as output_session:

            output_session.intf.lin_term = constants.LinTerm.ON
            output_session.intf.lin_master = True

            output_session.change_lin_schedule(2)

            def write_LIN(session, id, payload):
                """ Write LIN Frame to XNET Session."""

                print('Sending MasterReq Frame : ID:{} Payload:{}'.format(id,[hex(val) for val in payload]))
                frame = types.LinFrame(id, type=constants.FrameType.LIN_DATA, payload=bytearray(payload))
                output_session.frames.write([frame])


            def read_LIN(session):
                """ Read LIN Frame from XNET Session."""

                slave_frame, = input_session.frames.read(frame_type=types.LinFrame)
                print('Received SlaveResp Frame :{}'.format(slave_frame))
                data =[int(struct.unpack('B',val)[0]) for val in slave_frame.payload]
                print('SlaveResp Payload = {}'.format([hex(val) for val in data]))
                return data

            input_session.flush()
            # Wake up LIN Bus
            print('0) Waking up LIN Bus...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['Empty_Frame'])
            slave_frame, = input_session.frames.read(frame_type=types.LinFrame)
            time.sleep(0.1)


            # Configure IBS
            """ Process to configure Qnom
            1) Check Table state
            2) Switch Table OFF
            3) Chance C_nominal
            4) Change Batt Type to AGM
            5) Change U0 Min/Max
            6) Change IqBatt, keep IChargeMin
            7) Allow IBS to save all parameters (10s wait)
            8) Check Table State
            9) Check C_nominal
            10) Check U0 Min/Max
            11) Check IQbatt, IChargeMin
            """



            print('1) Check Table State...')
            # frame_count = input_session.frames.count()
            # print('frames in buffer = {}'.format(frame_count))

            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['BattTable_State'])
            time.sleep(0.25)
            read_LIN(input_session)


            print('2) Switch Table OFF...')
            ibs.set_switch_table_OnOff(state='Off')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['BattTable_OnOff'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('3) Change C_NOMINAL...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['BattCap_Write'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('4) Change Batt Type to AGM...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['BattType_Write'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('5) Change U0 MIN/MAX...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['U0_MinMax_Write'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('6) Change IqBatt, keep IChargeMin...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['IQbatt_Write'])
            time.sleep(0.25)
            read_LIN(input_session)


            print('7) Allow IBS to save all parameters (10s wait)...')

            for i in range(0,100):
                print '*',
                time.sleep(0.1)
            print('\n')

            print('8) Check Table State...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['BattTable_State'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('9) Check C_Nominal...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['BattCap_Read'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('10) Check Batt Type...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['BattType_Read'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('11) Check U0 MIN/MAX...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['U0_MinMax_Read'])
            time.sleep(0.25)
            read_LIN(input_session)

            print('12) Check IQbatt, IChargeMin...')
            write_LIN(output_session, ibs.MasterReqId, ibs.master_payloads['IQbatt_Read'])
            time.sleep(0.25)
            read_LIN(input_session)



            print('Done!')












if __name__ == '__main__':
    main()
