<template>
  <div class="min-h-screen bg-base-200 p-4">
    <div class="max-w-7xl mx-auto">
      <h1 class="text-4xl font-bold text-center mb-6">PlantBox Dashboard</h1>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div class="card bg-base-100 shadow-xl">
          <div class="card-body">
            <h2 class="card-title">Live Camera</h2>
            <img :src="cameraUrl" alt="Live Camera" class="w-full rounded-lg" />
          </div>
        </div>

        <div class="card bg-base-100 shadow-xl">
          <div class="card-body">
            <h2 class="card-title">YOLO Detection</h2>
            <img :src="yoloUrl" alt="YOLO Output" class="w-full rounded-lg" />
          </div>
        </div>
      </div>

      <div class="card bg-base-100 shadow-xl mb-4">
        <div class="card-body">
          <h2 class="card-title">Job Control</h2>
          <div class="flex items-center gap-4">
            <div class="flex-1">
              <div class="text-sm opacity-70">Status</div>
              <div class="font-semibold text-lg">{{ jobStatus }}</div>
            </div>
            <div class="flex gap-2">
              <button @click="startJob" :disabled="jobStatus === 'Running'" class="btn btn-success btn-sm">Start</button>
              <button @click="stopJob" :disabled="jobStatus === 'Stopped'" class="btn btn-error btn-sm">Stop</button>
            </div>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div class="card bg-base-100 shadow-xl">
          <div class="card-body">
            <h2 class="card-title">Motor Position</h2>
            <div class="space-y-2">
              <div class="flex justify-between">
                <span class="font-semibold">X:</span>
                <span>{{ motor.x.toFixed(2) }} 圈</span>
              </div>
              <div class="flex justify-between">
                <span class="font-semibold">Y:</span>
                <span>{{ motor.y.toFixed(2) }} 圈</span>
              </div>
              <div class="flex justify-between">
                <span class="font-semibold">Z:</span>
                <span>{{ motor.z.toFixed(2) }} 圈</span>
              </div>
            </div>
          </div>
        </div>

        <div class="card bg-base-100 shadow-xl">
          <div class="card-body">
            <h2 class="card-title">Servo Angles</h2>
            <div class="space-y-2">
              <div class="flex justify-between">
                <span class="font-semibold">Servo 1:</span>
                <span>{{ motor.servo_1.toFixed(1) }}°</span>
              </div>
              <div class="flex justify-between">
                <span class="font-semibold">Servo 2:</span>
                <span>{{ motor.servo_2.toFixed(1) }}°</span>
              </div>
              <div class="flex justify-between">
                <span class="font-semibold">Servo 3:</span>
                <span>{{ motor.servo_3.toFixed(1) }}°</span>
              </div>
            </div>
          </div>
        </div>

        <div class="card bg-base-100 shadow-xl">
          <div class="card-body">
            <h2 class="card-title">Sensor Data</h2>
            <div class="space-y-2">
              <div class="flex justify-between">
                <span class="font-semibold">Temperature:</span>
                <span>{{ sensors.temperature.toFixed(1) }}°C</span>
              </div>
              <div class="flex justify-between">
                <span class="font-semibold">Humidity:</span>
                <span>{{ sensors.humidity.toFixed(1) }}%</span>
              </div>
              <div class="flex justify-between">
                <span class="font-semibold">Soil Humidity:</span>
                <span>{{ sensors.soil_humidity.toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <div class="card bg-base-100 shadow-xl lg:col-span-3">
          <div class="card-body">
            <h2 class="card-title">Target Environment</h2>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div class="text-sm opacity-70">Watering</div>
                <div class="font-semibold">{{ targetEnv.watering_frequency?.toFixed(1) || 'N/A' }} days</div>
                <div class="text-xs">{{ targetEnv.watering_amount?.toFixed(0) || 'N/A' }} ml</div>
              </div>
              <div>
                <div class="text-sm opacity-70">Sunlight</div>
                <div class="font-semibold">{{ targetEnv.sunlight?.toFixed(1) || 'N/A' }} hrs/day</div>
              </div>
              <div>
                <div class="text-sm opacity-70">Temperature</div>
                <div class="font-semibold">{{ targetEnv.temperature?.toFixed(1) || 'N/A' }}°C</div>
              </div>
              <div>
                <div class="text-sm opacity-70">Fertilization</div>
                <div class="font-semibold">{{ targetEnv.fertilization_frequency?.toFixed(1) || 'N/A' }} days</div>
                <div class="text-xs">{{ targetEnv.fertilization_amount?.toFixed(0) || 'N/A' }} ml</div>
              </div>
              <div>
                <div class="text-sm opacity-70">Wind</div>
                <div class="font-semibold">{{ targetEnv.wind?.toFixed(0) || 'N/A' }}%</div>
              </div>
            </div>
          </div>
        </div>

        <div class="card bg-base-100 shadow-xl lg:col-span-3">
          <div class="card-body">
            <h2 class="card-title">Debug Controls</h2>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <h3 class="font-semibold mb-2">Motor Control</h3>
                <div class="space-y-2">
                  <div class="flex gap-2 items-center">
                    <label class="w-16">X:</label>
                    <input v-model.number="debugX" type="number" step="0.1" class="input input-sm input-bordered flex-1" />
                    <span class="text-xs opacity-70">0-9.5</span>
                  </div>
                  <div class="flex gap-2 items-center">
                    <label class="w-16">Y:</label>
                    <input v-model.number="debugY" type="number" step="0.1" class="input input-sm input-bordered flex-1" />
                    <span class="text-xs opacity-70">0-9.0</span>
                  </div>
                  <div class="flex gap-2 items-center">
                    <label class="w-16">Z:</label>
                    <input v-model.number="debugZ" type="number" step="0.1" class="input input-sm input-bordered flex-1" />
                    <span class="text-xs opacity-70">0-1.5</span>
                  </div>
                  <div class="flex gap-2 items-center">
                    <label class="w-16">Servo 1:</label>
                    <input v-model.number="debugServo1" type="number" step="1" class="input input-sm input-bordered flex-1" />
                    <span class="text-xs opacity-70">0-360</span>
                  </div>
                  <div class="flex gap-2 items-center">
                    <label class="w-16">Servo 2:</label>
                    <input v-model.number="debugServo2" type="number" step="1" class="input input-sm input-bordered flex-1" />
                    <span class="text-xs opacity-70">20-160</span>
                  </div>
                  <div class="flex gap-2 items-center">
                    <label class="w-16">Servo 3:</label>
                    <input v-model.number="debugServo3" type="number" step="1" class="input input-sm input-bordered flex-1" />
                    <span class="text-xs opacity-70">0-180</span>
                  </div>
                  <button @click="sendMotorCommand" class="btn btn-primary btn-sm w-full">Send Command</button>
                </div>
              </div>
              <div>
                <h3 class="font-semibold mb-2">Serial Monitor</h3>
                <div class="flex gap-2 mb-2">
                  <input v-model="serialCommand" @keyup.enter="sendSerialCommand" type="text" placeholder="Enter command..." class="input input-sm input-bordered flex-1" />
                  <button @click="sendSerialCommand" class="btn btn-primary btn-sm">Send</button>
                </div>
                <div class="bg-base-300 p-2 rounded h-48 overflow-y-auto font-mono text-xs">
                  <div v-for="(line, idx) in serialOutput" :key="idx">{{ line }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'

const cameraUrl = ref('/api/camera/stream')
const yoloUrl = ref('/api/yolo/stream')

const motor = ref({
  x: 0,
  y: 0,
  z: 0,
  servo_1: 0,
  servo_2: 0,
  servo_3: 0
})

const sensors = ref({
  temperature: 0,
  humidity: 0,
  soil_humidity: 0
})

const targetEnv = ref({})

const debugX = ref(0)
const debugY = ref(0)
const debugZ = ref(0)
const debugServo1 = ref(180)
const debugServo2 = ref(82.5)
const debugServo3 = ref(90)
const serialCommand = ref('')
const serialOutput = ref([])
const jobStatus = ref('stopped')

let socket = null

const startJob = async () => {
  try {
    const res = await fetch('/api/job/start', { method: 'POST' })
    const data = await res.json()
    if (!data.success) alert(data.error)
  } catch (e) {
    alert('Error: ' + e.message)
  }
}

const stopJob = async () => {
  try {
    const res = await fetch('/api/job/stop', { method: 'POST' })
    const data = await res.json()
    if (!data.success) alert(data.error)
  } catch (e) {
    alert('Error: ' + e.message)
  }
}

const sendMotorCommand = async () => {
  try {
    const res = await fetch('/api/motor/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        x: debugX.value,
        y: debugY.value,
        z: debugZ.value,
        servo_1: debugServo1.value,
        servo_2: debugServo2.value,
        servo_3: debugServo3.value
      })
    })
    const data = await res.json()
    if (!data.success) alert(data.error)
  } catch (e) {
    alert('Error: ' + e.message)
  }
}

const sendSerialCommand = async () => {
  if (!serialCommand.value.trim()) return
  try {
    await fetch('/api/serial/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: serialCommand.value })
    })
    serialCommand.value = ''
  } catch (e) {
    alert('Error: ' + e.message)
  }
}

onMounted(() => {
  socket = io('http://localhost:5000')

  socket.on('status_update', (data) => {
    if (data.motor) {
      motor.value = data.motor
    }
    if (data.sensors) {
      sensors.value = data.sensors
    }
    if (data.target_env) {
      targetEnv.value = data.target_env
    }
  })

  socket.on('serial_output', (data) => {
    serialOutput.value.push(data.line)
    if (serialOutput.value.length > 100) serialOutput.value.shift()
  })

  socket.on('job_status', (data) => {
    jobStatus.value = data.status
  })

  fetch('/api/status')
    .then(res => res.json())
    .then(data => {
      if (data.motor) motor.value = data.motor
      if (data.sensors) sensors.value = data.sensors
      if (data.target_env) targetEnv.value = data.target_env
      if (data.job_status) jobStatus.value = data.job_status
    })
})

onUnmounted(() => {
  if (socket) {
    socket.disconnect()
  }
})
</script>
