/*
【修改】：2026.2.7 - 移除第四自由度旋转舵机功能，保留机械爪+原有所有功能
机械爪：GPIO18，0°张开/60°闭合，速度80度/秒，严格限制0-60°
*/
#define RXD2 17
#define TXD2 16

//这些值敏感且影响大，不建议轻易改变
#define MOTOR_ADDR_1 1      //x轴方向的电机
#define MOTOR_ADDR_2 2      //y轴方向的电机
#define MOTOR_ADDR_3 3      //z轴方向的电机
#define MOTOR_ADDR_4 4      //x轴方向的电机
#define HOMING_SPEED_1 25   //x轴回零的速度
#define HOMING_SPEED_2 25   //y轴回零的速度
#define HOMING_SPEED_3 15   //z轴回零的速度
#define HOMING_SPEED_4 25   //x轴回零的速度需要和HOMING_SPEED_1一致
#define STALL_CURRENT 500   //上电自动回零的关键参数，堵转电流的阈值。较为玄学，不建议轻易改变。
#define PULSES_PER_REVOLUTION 3200 // 16细分下3200脉冲转1圈


// 坐标范围限制
const float MAX_X = 9.5;    // X轴最大坐标 (对应9圈)
const float MAX_Y = 9.0;    // Y轴最大坐标 (对应9圈)
const float MAX_Z = 1.5;    // Z轴最大坐标 (对应1.5圈)

// 当前坐标位置 (单位: 圈数)
float currentX = 0.0;
float currentY = 0.0;
float currentZ = 0.0;

// 舵机引脚和通道定义
const int servo_1_Pin = 4;
const int servo_2_Pin = 5;
const int servo_3_Pin = 6;
const int channel_1 = 0;
const int channel_2 = 1;
const int channel_3 = 2;

// 【保留】：机械爪开合舵机 引脚/通道定义
const int servo_claw_Pin = 21;    // 机械爪开合舵机引脚
const int channel_claw = 4;     // 机械爪舵机PWM通道（测试完成，固定4）

// 【保留】：机械爪开合角度常量（已测试完成，根据实际机械限位调整，避免损坏）
#define CLAW_OPEN_ANGLE 0.0     // 机械爪完全张开角度（测试后固定0°）
#define CLAW_CLOSE_ANGLE 60.0   // 机械爪完全闭合角度（测试后修改为60°，适配齿轮结构）
#define CLAW_MAX_SPEED 80.0     // 机械爪开合速度（测试后修改为80度/秒，齿轮结构更平稳）

// 湿度传感器引脚
#define HUMIDITY_SENSOR_PIN 3  // 3号引脚用于读取湿度值

// 舵机状态结构体
struct ServoState {
    float currentAngle;    
    float targetAngle;     
    float speed;           
    unsigned long lastUpdateTime;
    int lastPwmValue;
};

// 舵机状态初始化。建议舵机1的初始化角度270，舵机2初始角度30，舵机3初始角度可为任意值。
ServoState servo1 = {-1, 270, 150.0, 0, -1};
ServoState servo2 = {-1, 30, 120.0, 0, -1};
ServoState servo3 = {-1, 90, 150.0, 0, -1}; //设置舵机初始角度，以及运动速度

// 【保留】：机械爪舵机初始化
ServoState servo_claw = {-1, CLAW_OPEN_ANGLE, CLAW_MAX_SPEED, 0, -1}; // 机械爪初始张开（0°），速度80

// 定义继电器控制引脚
#define RELAY1_PIN 9
#define RELAY2_PIN 10
#define RELAY3_PIN 11
#define PWM_PIN 7

// 控制水泵功率大小的PWM
#define PWM_CHANNEL 3  // 使用PWM通道3
#define PWM_FREQ 5000  // 5kHz频率
#define PWM_RESOLUTION 8 // 8位分辨率 (0-255)

// 继电器状态变量
bool relay1State = false;
bool relay2State = false;
bool relay3State = false;
int pwmValue = 0;

// 湿度读取相关变量
unsigned long lastHumidityReadTime = 0;
const unsigned long HUMIDITY_READ_INTERVAL = 2000; // 2秒读取一次湿度

// 函数声明
void setupHomingParameters(uint8_t addr, uint16_t homingSpeed, uint8_t direction);//设置步进电机回零的参数 parameter1：步进电机地址   parameter2：归零速度    parameter3：回零的方向
void executeAutoHoming(); //执行234号步进电机的回零操作
void Emm_V5_Origin_Modify_Params(uint8_t addr, bool svF, uint8_t o_mode, 
    uint8_t o_dir, uint16_t o_vel, uint32_t o_tm, uint16_t sl_vel, 
    uint16_t sl_ma, uint16_t sl_ms, bool potF);//步进电机回零模式的关键参数设置
void Emm_V5_Origin_Trigger_Return(uint8_t addr, uint8_t o_mode, bool snF);//执行单个步进电机的回零操作
void Emm_V5_Stop_Now(uint8_t addr);//步进电机停止操作，本程序未使用
float constrainValue(float value, float minVal, float maxVal);//步进电机运动圈数限制
void moveToCoordinate(float targetX, float targetY, float targetZ);//xyz轴运动指令，parameter1：x轴目标坐标   parameter2：y轴目标坐标    parameter3：z轴目标坐标
void Emm_V5_Pos_Control(uint8_t addr, uint8_t dir, uint16_t vel, uint8_t acc, uint32_t clk, bool raF, bool snF);//步进电机的位置模式
void updateServo(ServoState &servo, int channel, float maxAngle);//舵机目标角度
void readHumiditySensor(); //湿度值读取
void executeReadCommand(); //在串口输入“read”，系统执行这个函数。执行读取操作，运行步进电机和舵机，配合温湿度传感器读取

// 【保留】：机械爪快捷控制函数声明
void controlClaw(bool isClose);

void setup() {
    Serial.begin(115200);
    Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
    delay(10);
    
    // 初始化机械臂的舵机PWM
    ledcSetup(channel_1, 50, 12);  
    ledcAttachPin(servo_1_Pin, channel_1);
    
    ledcSetup(channel_2, 50, 12);  
    ledcAttachPin(servo_2_Pin, channel_2);
    
    ledcSetup(channel_3, 50, 12);
    ledcAttachPin(servo_3_Pin, channel_3);

    // 【保留】：初始化机械爪舵机PWM
    ledcSetup(channel_claw, 50, 12);  // 50Hz频率，12位分辨率（与原有舵机一致）
    ledcAttachPin(servo_claw_Pin, channel_claw);
       
    // 设置继电器控制引脚为输出模式
    pinMode(RELAY1_PIN, OUTPUT);
    pinMode(RELAY2_PIN, OUTPUT);
    pinMode(RELAY3_PIN, OUTPUT);
    
    // 配置PWM
    ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
    ledcAttachPin(PWM_PIN, PWM_CHANNEL);
    ledcWrite(PWM_CHANNEL, 0); // 初始PWM值为0
    
    // 初始状态下关闭所有继电器
    digitalWrite(RELAY1_PIN, LOW);
    digitalWrite(RELAY2_PIN, LOW);
    digitalWrite(RELAY3_PIN, LOW);
    
    // 设置湿度传感器引脚为输入模式
    pinMode(HUMIDITY_SENSOR_PIN, INPUT);
    
    // 然后进行电机复位
    Serial.println("开始电机复位...");
    // 配置电机1的回零参数（CCW方向）
    setupHomingParameters(MOTOR_ADDR_1, HOMING_SPEED_1, 0); 
    // 配置电机4的回零参数（CW方向）
    setupHomingParameters(MOTOR_ADDR_4, HOMING_SPEED_4, 1); 
    // 配置电机2的回零参数（CW方向）
    setupHomingParameters(MOTOR_ADDR_2, HOMING_SPEED_2, 0); 
    // 配置电机3的回零参数（CW方向）
    setupHomingParameters(MOTOR_ADDR_3, HOMING_SPEED_3, 0); 
    
    Emm_V5_Origin_Trigger_Return(MOTOR_ADDR_3, 2, false);//先执行z轴的回零
    delay(3000);
    
    //舵机角度初始化
    updateServo(servo1, channel_1, 360);
    updateServo(servo2, channel_2, 165);
    updateServo(servo3, channel_3, 180);
    
    // 【保留】：机械爪初始化
    updateServo(servo_claw, channel_claw, 180); // 机械爪张开（0°）

    executeAutoHoming();//执行x轴和y轴的回零

    Serial.println("=== 三轴坐标控制程序（保留机械爪功能）===");
    Serial.println("输入格式1 (步进电机和所有舵机): X,Y,Z,servo1,servo2,servo3,clawAngle");
    Serial.println("例如: 5.0,3.0,0.8,180,90,90,0 (claw=0°张开)");
    Serial.println("坐标范围: X[0-9.5], Y[0-9], Z[0-1.5]");
    Serial.println("舵机范围: servo1[0-360], servo2[0-165], servo3[0-180], claw[0-60]");
    Serial.println("单位: 坐标=圈数，舵机=角度");
    Serial.print("当前坐标: X=");
    Serial.print(currentX);
    Serial.print(", Y=");
    Serial.print(currentY);
    Serial.print(", Z=");
    Serial.println(currentZ);
    
    Serial.println("输入格式2 (继电器和PWM): <relay1>,<relay_select>,<pwm_value>");
    Serial.println("Parameter 1 (Relay1): 0-OFF, 1-ON");
    Serial.println("Parameter 2 (Relay选择): 0-全部关闭, 1-Relay2开启, 2-Relay3开启");
    Serial.println("Parameter 3 (PWM): 0-255 (0=OFF, 255=Full power)");
    Serial.println("Example: '1,2,128' - Relay1 ON, Relay3 ON, PWM=128");
    
    Serial.println("特殊命令: 'read' - 执行读取操作(机械爪自动张开)");
    Serial.println("=======================");
}

void loop() {
    // 检查串口是否有数据输入
    if (Serial.available() > 0) {
        String input = Serial.readStringUntil('\n');
        input.trim();
        
        // 检查是否为特殊命令 "read"
        if (input.equalsIgnoreCase("read")) {
            executeReadCommand();
            return;
        }
        
        // 计算逗号数量
        int commaCount = 0;
        for (int i = 0; i < input.length(); i++) {
            if (input.charAt(i) == ',') commaCount++;
        }
        
        // 根据逗号数量判断命令类型
        if (commaCount == 6) { // 修改：从7个逗号改为6个逗号（移除s4参数）
            // 步进电机和舵机控制命令（7参数：X,Y,Z,s1,s2,s3,claw）
            
            int firstCommaIndex = input.indexOf(',');
            int secondCommaIndex = input.indexOf(',', firstCommaIndex + 1);
            int thirdCommaIndex = input.indexOf(',', secondCommaIndex + 1);
            int fourthCommaIndex = input.indexOf(',', thirdCommaIndex + 1);
            int fifthCommaIndex = input.indexOf(',', fourthCommaIndex + 1);
            int sixthCommaIndex = input.indexOf(',', fifthCommaIndex + 1);

            if (firstCommaIndex != -1 && secondCommaIndex != -1 && 
                thirdCommaIndex != -1 && fourthCommaIndex != -1 && 
                fifthCommaIndex != -1 && sixthCommaIndex != -1) {
                
                String xStr = input.substring(0, firstCommaIndex);
                String yStr = input.substring(firstCommaIndex + 1, secondCommaIndex);
                String zStr = input.substring(secondCommaIndex + 1, thirdCommaIndex);
                String servo1Str = input.substring(thirdCommaIndex + 1, fourthCommaIndex);
                String servo2Str = input.substring(fourthCommaIndex + 1, fifthCommaIndex);
                String servo3Str = input.substring(fifthCommaIndex + 1, sixthCommaIndex);
                String clawStr = input.substring(sixthCommaIndex + 1); // 机械爪开合角度
                
                float targetX = constrainValue(xStr.toFloat(), 0, MAX_X);
                float targetY = constrainValue(yStr.toFloat(), 0, MAX_Y);
                float targetZ = constrainValue(zStr.toFloat(), 0, MAX_Z);

                // 移动到目标坐标
                moveToCoordinate(targetX, targetY, targetZ);

                delay(1000);//接受到命令后，xyz轴先运动1s，再执行其他操作
                
                // constrain限制舵机的角度值（原舵机保留）
                servo1.targetAngle = constrain(servo1Str.toInt(), 0, 360);
                servo2.targetAngle = constrain(servo2Str.toInt(), 0, 165);//舵机2值限制在0-165之间
                servo3.targetAngle = constrain(servo3Str.toInt(), 0, 180);
                
                // 【保留】：机械爪角度（严格限制0-60°，避免超限位损坏）
                servo_claw.targetAngle = constrain(clawStr.toFloat(), CLAW_OPEN_ANGLE, CLAW_CLOSE_ANGLE);

                // 串口打印更新（移除第四自由度相关信息）
                Serial.print("目标坐标: X=");
                Serial.print(targetX);
                Serial.print(", Y=");
                Serial.print(targetY);
                Serial.print(", Z=");
                Serial.print(targetZ);
                Serial.print(" | 舵机: s1=");
                Serial.print(servo1.targetAngle);
                Serial.print(", s2=");
                Serial.print(servo2.targetAngle);
                Serial.print(", s3=");
                Serial.print(servo3.targetAngle);
                Serial.print(", 机械爪=");
                Serial.print(servo_claw.targetAngle);
                Serial.println(servo_claw.targetAngle == CLAW_OPEN_ANGLE ? "(张开)" : "(闭合/半开合)");
                
            } else {
                // 更新错误提示格式（移除第四自由度参数）
                Serial.println("错误: 输入格式不正确，请使用 'X,Y,Z,servo1,servo2,servo3,clawAngle' 格式");
                Serial.println("例如: 5.0,3.0,0.8,180,90,90,0 （0=机械爪张开）");
            }
        }
        else if (commaCount == 2) {
            // 继电器和PWM控制命令（原逻辑完全保留，无修改）
            int firstComma = input.indexOf(',');
            int secondComma = input.indexOf(',', firstComma + 1);
            
            if (firstComma != -1 && secondComma != -1) {
                String firstVal = input.substring(0, firstComma);
                String secondVal = input.substring(firstComma + 1, secondComma);
                String thirdVal = input.substring(secondComma + 1);
                
                int relay1Cmd = firstVal.toInt();
                int relaySelectCmd = secondVal.toInt();
                int pwmCmd = thirdVal.toInt();
                
                // 处理继电器和PWM控制命令
                // 验证PWM值范围
                if (pwmCmd < 0 || pwmCmd > 255) {
                    Serial.println("错误: PWM值必须在0-255之间");
                    return;
                }
                
                // 验证继电器命令范围
                if (relay1Cmd < 0 || relay1Cmd > 1) {
                    Serial.println("错误: Relay1命令必须是0或1");
                    return;
                }
                
                if (relaySelectCmd < 0 || relaySelectCmd > 2) {
                    Serial.println("错误: Relay选择命令必须是0, 1或2");
                    return;
                }
                
                // 设置继电器1状态
                relay1State = (relay1Cmd == 1);
                digitalWrite(RELAY1_PIN, relay1State ? HIGH : LOW);
                Serial.print("Relay1: ");
                Serial.println(relay1State ? "ON" : "OFF");
                
                // 设置继电器2和3状态（根据修改后的逻辑）
                relay2State = false;
                relay3State = false;
                
                switch (relaySelectCmd) {
                    case 0:
                        // 全部关闭
                        Serial.println("Relay2: OFF, Relay3: OFF");
                        break;
                    case 1:
                        // 仅开启继电器2
                        relay2State = true;
                        Serial.println("Relay2: ON, Relay3: OFF");
                        break;
                    case 2:
                        // 仅开启继电器3
                        relay3State = true;
                        Serial.println("Relay2: OFF, Relay3: ON");
                        break;
                }
                
                digitalWrite(RELAY2_PIN, relay2State ? HIGH : LOW);
                digitalWrite(RELAY3_PIN, relay3State ? HIGH : LOW);
                
                // 设置PWM值
                pwmValue = pwmCmd;
                ledcWrite(PWM_CHANNEL, pwmValue);
                Serial.print("PWM set to: ");
                Serial.println(pwmValue);
                
                Serial.println("----------------------------------------");
            } else {
                Serial.println("错误: 输入格式不正确，请使用 '<relay1>,<relay_select>,<pwm_value>' 格式");
                Serial.println("例如: '1,2,128' - Relay1 ON, Relay3 ON, PWM=128");
            }
        }
        else {
            // 更新未知命令提示（移除第四自由度参数）
            Serial.println("错误: 未知的命令格式");
            Serial.println("请使用以下两种格式之一:");
            Serial.println("1. 步进电机和所有舵机控制: X,Y,Z,servo1,servo2,servo3,clawAngle (7个参数)");
            Serial.println("   舵机范围: claw[0-60](机械爪0=张开60=闭合)");
            Serial.println("2. 继电器和PWM控制: <relay1>,<relay_select>,<pwm_value> (3个参数)");
            Serial.println("3. 特殊命令: 'read' - 执行读取操作(机械爪自动张开)");
        }
    }
    
    // 更新舵机位置（移除第四自由度舵机更新）
    updateServo(servo1, channel_1, 360);
    updateServo(servo2, channel_2, 165);
    updateServo(servo3, channel_3, 180); 
    updateServo(servo_claw, channel_claw, 180);

    // 定期读取湿度传感器（原逻辑完全保留）
    unsigned long currentTime = millis();
    if (currentTime - lastHumidityReadTime >= HUMIDITY_READ_INTERVAL) {
        readHumiditySensor();
        lastHumidityReadTime = currentTime;
    }
    
    delay(10); // 短暂延迟
}

// 执行读取命令的特殊功能（移除第四自由度归位逻辑）
void executeReadCommand() {
    Serial.println("执行读取命令...");

    servo1.targetAngle = 270;
    servo2.targetAngle = 90;
    servo_claw.targetAngle = CLAW_OPEN_ANGLE;
    
    updateServo(servo1, channel_1, 360);
    updateServo(servo2, channel_2, 165);
    updateServo(servo_claw, channel_claw, 180);
    delay(700);
    
    // Z轴运动到1圈位置（实际代码中是0.4圈，保留原有逻辑）
    Serial.println("Z轴运动到检测位置(0.4圈）");
    moveToCoordinate(currentX, currentY, 0.4);
    delay(2000);
    
    moveToCoordinate(currentX, currentY, 0);//读取数据两秒钟，z轴再回到零位置。
    delay(500);
    servo2.targetAngle = 30;
    // 读取完成后，机械爪保持张开，防止夹取异物
    servo_claw.targetAngle = CLAW_OPEN_ANGLE;
    
    updateServo(servo2, channel_2, 165);
    updateServo(servo_claw, channel_claw, 180);//机械臂倾斜，防止后续移动撞翻花盆
    Serial.println("读取命令执行完成(机械爪保持张开)");
}

// 【保留】：机械爪快捷控制函数
void controlClaw(bool isClose) {
    if (isClose) {
        servo_claw.targetAngle = CLAW_CLOSE_ANGLE;
        Serial.println("机械爪：完全闭合(60°,齿轮结构适配)");
    } else {
        servo_claw.targetAngle = CLAW_OPEN_ANGLE;
        Serial.println("机械爪:完全张开(0°)");
    }
    updateServo(servo_claw, channel_claw, 180);
}

// 读取湿度传感器值（原逻辑完全保留，无修改）
void readHumiditySensor() {
    int sensorValue = analogRead(HUMIDITY_SENSOR_PIN);
    // 将模拟值转换为湿度百分比（根据传感器特性调整转换公式）
    float humidity = 100.0-map(sensorValue, 0, 4095, 0, 100); // ESP32的ADC是12位，范围0-4095
    
    Serial.print("湿度值: ");
    Serial.print(humidity);
    Serial.println("%");
}

// 配置回零参数（增加方向参数，原逻辑完全保留）
void setupHomingParameters(uint8_t addr, uint16_t homingSpeed, uint8_t direction) {
    Emm_V5_Origin_Modify_Params(
        addr,           // 地址
        true,           // 保存参数
        2,              // 堵转检测模式
        direction,      // 方向（0=CW, 1=CCW）
        homingSpeed,    // 回零速度（使用传入的速度参数）
        20000,          // 20秒超时
        5,             // 速度阈值
        STALL_CURRENT,  // 电流阈值
        50,             // 检测时间
        false           // 回零后保持使能
    );
    delay(50);
}

// 执行自动回零（同时触发三个电机，xy轴进行回零操作，原逻辑完全保留）
void executeAutoHoming() {
    Serial.println("同时执行三个电机堵转检测回零...");
    Serial.println("等待20s复位");
   
    Emm_V5_Origin_Trigger_Return(MOTOR_ADDR_1, 2, false); 
    delay(3);
    Emm_V5_Origin_Trigger_Return(MOTOR_ADDR_4, 2, false);
    delay(3);
    Emm_V5_Origin_Trigger_Return(MOTOR_ADDR_2, 2, false);
    delay(20000);
}

// EMM_V5 驱动函数实现（原逻辑完全保留，无修改）
void Emm_V5_Origin_Modify_Params(uint8_t addr, bool svF, uint8_t o_mode, 
    uint8_t o_dir, uint16_t o_vel, uint32_t o_tm, uint16_t sl_vel, 
    uint16_t sl_ma, uint16_t sl_ms, bool potF) {
    
    uint8_t cmd[20] = {
        addr, 0x4C, 0xAE, svF, o_mode, o_dir,
        (uint8_t)(o_vel >> 8), (uint8_t)(o_vel),
        (uint8_t)(o_tm >> 24), (uint8_t)(o_tm >> 16), 
        (uint8_t)(o_tm >> 8), (uint8_t)(o_tm),
        (uint8_t)(sl_vel >> 8), (uint8_t)(sl_vel),
        (uint8_t)(sl_ma >> 8), (uint8_t)(sl_ma),
        (uint8_t)(sl_ms >> 8), (uint8_t)(sl_ms),
        potF, 0x6B
    };
    Serial2.write(cmd, 20);
}

void Emm_V5_Origin_Trigger_Return(uint8_t addr, uint8_t o_mode, bool snF) {
    uint8_t cmd[5] = {addr, 0x9A, o_mode, snF, 0x6B};
    Serial2.write(cmd, 5);
}

void Emm_V5_Stop_Now(uint8_t addr) {
    uint8_t cmd[4] = {addr, 0xFE, 0x98, 0x6B};
    Serial2.write(cmd, 4);
}

// xyz轴限制数值在指定范围内（原逻辑完全保留）
float constrainValue(float value, float minVal, float maxVal) {
    if (value < minVal) {
        Serial.print("警告: 坐标值 ");
        Serial.print(value);
        Serial.print(" 小于最小值 ");
        Serial.print(minVal);
        Serial.println("，已调整为最小值");
        return minVal;
    } else if (value > maxVal) {
        Serial.print("警告: 坐标值 ");
        Serial.print(value);
        Serial.print(" 大于最大值 ");
        Serial.print(maxVal);
        Serial.println("，已调整为最大值");
        return maxVal;
    }
    return value;
}

// 步进电机坐标移动（原逻辑完全保留，无修改）
void moveToCoordinate(float targetX, float targetY, float targetZ) {

    // 计算绝对脉冲数（正坐标转换为负脉冲）
    uint32_t pulsesX = (uint32_t)(targetX * PULSES_PER_REVOLUTION);
    uint32_t pulsesY = (uint32_t)(targetY * PULSES_PER_REVOLUTION);
    uint32_t pulsesZ = (uint32_t)(targetZ * PULSES_PER_REVOLUTION);
    
    // 发送绝对位置控制命令
    // X轴电机1和电机4 - 使用负方向
    if (targetX != currentX) {
        Serial.print("X轴电机1: ");
        Serial.print(targetX);
        Serial.print("圈, 脉冲数: ");
        Serial.println(pulsesX);
        Emm_V5_Pos_Control(1, 1, 150, 0, pulsesX, true, 0); // 方向1表示负方向
        delay(5);
        
        Serial.print("X轴电机4: ");
        Serial.print(targetX);
        Serial.print("圈, 脉冲数: ");
        Serial.println(pulsesX);
        Emm_V5_Pos_Control(4, 0, 150, 0, pulsesX, true, 0); // 方向0表示负方向
    }
    delay(5);
    
    // Y轴电机2 - 使用负方向
    if (targetY != currentY) {
        Serial.print("Y轴电机2: ");
        Serial.print(targetY);
        Serial.print("圈, 脉冲数: ");
        Serial.println(pulsesY);
        Emm_V5_Pos_Control(2, 1, 150, 0, pulsesY, true, 0); // 方向1表示负方向
    }
    delay(5);
    
    // Z轴电机3 - 使用负方向
    if (targetZ != currentZ) {
        Serial.print("Z轴电机3: ");
        Serial.print(targetZ);
        Serial.print("圈, 脉冲数: ");
        Serial.println(pulsesZ);
        Emm_V5_Pos_Control(3, 1, 50, 0, pulsesZ, true, 0); // 方向1表示负方向
    }
    
    // 更新当前坐标
    currentX = targetX;
    currentY = targetY;
    currentZ = targetZ;
    
    Serial.print("新坐标: X=");
    Serial.print(currentX);
    Serial.print(", Y=");
    Serial.print(currentY);
    Serial.print(", Z=");
    Serial.println(currentZ);
}

// 步进电机位置控制（原逻辑完全保留，无修改）
void Emm_V5_Pos_Control(uint8_t addr, uint8_t dir, uint16_t vel, uint8_t acc, uint32_t clk, bool raF, bool snF) {
    uint8_t cmd[16] = {0};
    // 装载命令
    cmd[0]  =  addr;                      // 地址
    cmd[1]  =  0xFD;                      // 功能码
    cmd[2]  =  dir;                       // 方向 (1=负方向，0=正方向)
    cmd[3]  =  (uint8_t)(vel >> 8);       // 速度(RPM)高8位字节
    cmd[4]  =  (uint8_t)(vel >> 0);       // 速度(RPM)低8位字节 
    cmd[5]  =  acc;                       // 加速度，注意：0是直接启动
    cmd[6]  =  (uint8_t)(clk >> 24);      // 脉冲数(bit24 - bit31)
    cmd[7]  =  (uint8_t)(clk >> 16);      // 脉冲数(bit16 - bit23)
    cmd[8]  =  (uint8_t)(clk >> 8);       // 脉冲数(bit8  - bit15)
    cmd[9]  =  (uint8_t)(clk >> 0);       // 脉冲数(bit0  - bit7 )
    cmd[10] =  raF;                       // 相位/绝对标志，false为相对运动，true为绝对值运动
    cmd[11] =  snF;                       // 多机同步运动标志，false为不启用，true为启用
    cmd[12] =  0x6B;                      // 校验字节 
    // 发送命令
    Serial2.write(cmd, 13);
}

// 更新舵机位置（原逻辑完全保留，平滑调速核心，适配所有保留舵机）
void updateServo(ServoState &servo, int channel, float maxAngle) {
    unsigned long currentTime = millis();
    float deltaTime = (currentTime - servo.lastUpdateTime) / 1000.0;
    
    if (deltaTime < 0.01) return;
    servo.lastUpdateTime = currentTime;
    
    float angleDiff = servo.targetAngle - servo.currentAngle;
    if (abs(angleDiff) < 1.0) {
        servo.currentAngle = servo.targetAngle;
        return;
    }
    
    float moveDistance = servo.speed * deltaTime;
    if (angleDiff > 0) {
        servo.currentAngle += min(moveDistance, angleDiff);
    } else {
        servo.currentAngle += max(-moveDistance, angleDiff);
    }
    
    servo.currentAngle = constrain(servo.currentAngle, 0, maxAngle);
    
    int pwmValue = round(map(servo.currentAngle, 0, maxAngle, 102, 512));
    
    if (pwmValue != servo.lastPwmValue) {
        servo.lastPwmValue = pwmValue;
        ledcWrite(channel, pwmValue);
    }
}


