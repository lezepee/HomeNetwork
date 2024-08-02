import json
from Device import *
from enum import IntEnum


class StateRinging(IntEnum):
    # 서브폰의 호출 상태
    IDLE = 0
    FRONT = 1  # 현관문 초인종
    COMMUNAL = 2  # 공동출입문


class StateDoorLock(IntEnum):
    Unsecured = 0
    Secured = 1
    Jammed = 2
    Unknown = 3


class SubPhone(Device):
    state_streaming: int = 0
    state_ringing: StateRinging = StateRinging.IDLE
    state_ringing_prev: StateRinging = StateRinging.IDLE
    state_doorlock: StateDoorLock = StateDoorLock.Secured

    # 세대현관문, 공동현관문 분리
    state_lock_front: StateDoorLock = StateDoorLock.Secured
    state_ringing_front: int = 0
    state_ringing_front_prev: int = 0
    state_lock_communal: StateDoorLock = StateDoorLock.Secured
    state_ringring_communal: int = 0
    state_ringring_communal_prev: int = 0

    def __init__(self, name: str = 'SubPhone', index: int = 0, room_index: int = 0):
        super().__init__(name, index, room_index)
        self.dev_type = DeviceType.SUBPHONE
        self.unique_id = f'subphone_{self.room_index}_{self.index}'
        self.mqtt_publish_topic = f'home/state/subphone/{self.room_index}/{self.index}'
        self.mqtt_subscribe_topic = f'home/command/subphone/{self.room_index}/{self.index}'
        self.sig_state_streaming = Callback(int)
        self.enable_streaming = True
        self.streaming_config = {
            'conf_file_path': '',
            'feed_path': '',
            'input_device': '/dev/video0',
            'frame_rate': 24,
            'width': 320,
            'height': 240,
        }
    
    def setDefaultName(self):
        self.name = 'SubPhone'

    def publishMQTT(self):
        if self.mqtt_client is None:
            return

        obj = {
            "streaming_state": self.state_streaming,
            "doorlock_state": self.state_doorlock.name,  # 도어락은 상태 조회가 안되고 '열기' 기능만 존재한다
            "lock_front_state": self.state_lock_front.name,
            "lock_communal_state": self.state_lock_communal.name,
        }
        self.mqtt_client.publish(self.mqtt_publish_topic, json.dumps(obj), 1)
        obj = {"state": self.state_lock_front.name}
        self.mqtt_client.publish(self.mqtt_publish_topic + '/doorlock/front', json.dumps(obj), 1)
        obj = {"state": self.state_lock_communal.name}
        self.mqtt_client.publish(self.mqtt_publish_topic + '/doorlock/communal', json.dumps(obj), 1)

        if not self.init:
            self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell', 'OFF', 1)
            obj = {"state": 0}
            self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell/front', json.dumps(obj), 1)
            self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell/communal', json.dumps(obj), 1)

        if self.state_ringing != self.state_ringing_prev:  # 초인종 호출 상태 알림이 반복적으로 뜨는 것 방지 
            # writeLog(f"Ringing Publish: Prev={self.state_ringing.name}, Current={self.state_ringing_prev.name}", self)
            if self.state_ringing in [StateRinging.FRONT, StateRinging.COMMUNAL]:
                self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell', 'ON', 1)
            else:
                self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell', 'OFF', 1)
        
        if self.state_ringing_front != self.state_ringing_front_prev:
            writeLog(f"Front Door Ringing State: Prev={bool(self.state_ringing_front_prev)}, Current={bool(self.state_ringing_front)}", self)
            obj = {"state": self.state_ringing_front}
            self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell/front', json.dumps(obj), 1)

        if self.state_ringring_communal != self.state_ringring_communal_prev:
            writeLog(f"Communal Door Ringing State: Prev={bool(self.state_ringring_communal_prev)}, Current={bool(self.state_ringring_communal)}", self)
            obj = {"state": self.state_ringring_communal}
            self.mqtt_client.publish(self.mqtt_publish_topic + '/doorbell/communal', json.dumps(obj), 1)

    def configMQTT(self, retain: bool = False):
        if self.mqtt_client is None:
            return
        
        topic = f'{self.ha_discovery_prefix}/lock/{self.unique_id}/config'
        obj = {
            "name": self.name + " Doorlock",
            "object_id": self.unique_id + "_doorlock",
            "unique_id": self.unique_id + "_doorlock",
            "state_topic": self.mqtt_publish_topic,
            "command_topic": self.mqtt_subscribe_topic,
            "value_template": '{{ value_json.doorlock_state }}',
            "payload_lock": '{ "doorlock_state": "Secured" }',
            "payload_unlock": '{ "doorlock_state": "Unsecured" }',
            "state_locked": "Secured",
            "state_unlocked": "Unsecured",
            "state_jammed": "Jammed",
            "icon": "mdi:door-closed-lock",
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1, retain)
        
        # 세대현관문, 공동현관문 분리
        topic = f'{self.ha_discovery_prefix}/lock/{self.unique_id}_front/config'
        obj = {
            "name": self.name + " Lock (Front)",
            "object_id": self.unique_id + "_lock_front",
            "unique_id": self.unique_id + "_lock_front",
            "state_topic": self.mqtt_publish_topic + '/doorlock/front',
            "command_topic": self.mqtt_subscribe_topic,
            "value_template": '{{ value_json.state }}',
            "payload_lock": '{ "lock_front_state": "Secured" }',
            "payload_unlock": '{ "lock_front_state": "Unsecured" }',
            "state_locked": "Secured",
            "state_unlocked": "Unsecured",
            "state_jammed": "Jammed",
            "icon": "mdi:door-closed-lock",
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1)

        topic = f'{self.ha_discovery_prefix}/binary_sensor/{self.unique_id}_front/config'
        obj = {
            "name": self.name + " Ringing (front)",
            "object_id": self.unique_id + "_ringing_front",
            "unique_id": self.unique_id + "_ringing_front",
            "state_topic": self.mqtt_publish_topic + '/doorbell/front',
            "value_template": '{ "state": {{ value_json.state }} }',
            "payload_on": '{ "state": 1 }',
            "payload_off": '{ "state": 0 }',
            "device_class": "sound",
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1)

        topic = f'{self.ha_discovery_prefix}/lock/{self.unique_id}_communal/config'
        obj = {
            "name": self.name + " Lock (Communal)",
            "object_id": self.unique_id + "_lock_communal",
            "unique_id": self.unique_id + "_lock_communal",
            "state_topic": self.mqtt_publish_topic + '/doorlock/communal',
            "command_topic": self.mqtt_subscribe_topic,
            "value_template": '{{ value_json.state }}',
            "payload_lock": '{ "lock_communal_state": "Secured" }',
            "payload_unlock": '{ "lock_communal_state": "Unsecured" }',
            "state_locked": "Secured",
            "state_unlocked": "Unsecured",
            "state_jammed": "Jammed",
            "icon": "mdi:door-closed-lock",
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1)

        topic = f'{self.ha_discovery_prefix}/binary_sensor/{self.unique_id}_communal/config'
        obj = {
            "name": self.name + " Ringing (Communal)",
            "object_id": self.unique_id + "_ringing_communal",
            "unique_id": self.unique_id + "_ringing_communal",
            "state_topic": self.mqtt_publish_topic + '/doorbell/communal',
            "value_template": '{ "state": {{ value_json.state }} }',
            "payload_on": '{ "state": 1 }',
            "payload_off": '{ "state": 0 }',
            "device_class": "sound",
        }
        self.mqtt_client.publish(topic, json.dumps(obj), 1)

    def updateState(self, _: int, **kwargs):
        streaming = kwargs.get('streaming')
        if streaming is not None:
            self.state_streaming = streaming
            self.sig_state_streaming.emit(self.state_streaming)
            self.publishMQTT()
            writeLog(f"Streaming: {bool(self.state_streaming)}", self)

        ringing_front = kwargs.get('ringing_front')
        if ringing_front is not None:
            if ringing_front:
                self.state_ringing = StateRinging.FRONT
                self.state_ringing_front = 1
            else:
                self.state_ringing = StateRinging.IDLE
                self.state_ringing_front = 0
            self.publishMQTT()
            self.state_ringing_prev = self.state_ringing
            self.state_ringing_front_prev = self.state_ringing_front
            writeLog(f"Ringing: {self.state_ringing.name}", self)

        ringing_communal = kwargs.get('ringing_communal')
        if ringing_communal is not None:
            if ringing_communal:
                self.state_ringing = StateRinging.COMMUNAL
                self.state_ringring_communal = 1
            else:
                self.state_ringing = StateRinging.IDLE
                self.state_ringring_communal = 0
            self.publishMQTT()
            self.state_ringing_prev = self.state_ringing
            self.state_ringring_communal_prev = self.state_ringring_communal
            writeLog(f"Ringing: {self.state_ringing.name}", self)

        doorlock = kwargs.get('doorlock')
        if doorlock is not None:
            self.state_doorlock = StateDoorLock(doorlock)
            self.publishMQTT()
            # writeLog(f"DoorLock: {self.state_doorlock.name}", self)

        lock_front = kwargs.get('lock_front')
        if lock_front is not None:
            self.state_lock_front = StateDoorLock(lock_front)
            self.publishMQTT()
            writeLog(f"Lock Front: {self.state_lock_front.name}", self)

        lock_communal = kwargs.get('lock_communal')
        if lock_communal is not None:
            self.state_lock_communal = StateDoorLock(lock_communal)
            self.publishMQTT()
            writeLog(f"Lock Communal: {self.state_lock_communal.name}", self)
        
        if not self.init:
            self.publishMQTT()
            self.init = True

    def makePacketCommon(self, header: int) -> bytearray:
        return bytearray([0x7F, max(0, min(0xFF, header)), 0x00, 0x00, 0xEE])

    def makePacketSetVideoStreamingState(self, state: int) -> bytearray:
        if state:
            if self.state_ringing == StateRinging.FRONT:
                # 현관 초인종 카메라 영상 서브폰 우회
                return self.makePacketCommon(0xB7)
            elif self.state_ringing == StateRinging.COMMUNAL:
                # 공동현관문 영상 우회
                return self.makePacketCommon(0x5F)
            else:
                # 단순 문열기용 (주방 서브폰 활성화)
                return self.makePacketCommon(0xB9)
        else:
            if self.state_ringing == StateRinging.FRONT:
                # 현관 초인종 카메라 영상 서브폰 우회 종료
                return self.makePacketCommon(0xB8)
            elif self.state_ringing == StateRinging.COMMUNAL:
                # 공동현관문 영상 우회 종료
                return self.makePacketCommon(0x60)
            else:
                # 단순 문열기용 (주방 서브폰 활성화)
                return self.makePacketCommon(0xBA)

    def makePacketOpenFrontDoor(self) -> bytearray:
        # 현관 초인종 카메라 영상이 서브폰으로 우회된 상태에서 도어락 해제
        return self.makePacketCommon(0xB4)

    def makePacketOpenCommunalDoor(self) -> bytearray:
        # 공동현관문 호출 후 카메라 영상이 우회된 상태에서 열림 명령
        return self.makePacketCommon(0x61)
