import { createApp } from 'vue'
import type { Plugin } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import {
  Affix,
  Alert,
  BackTop,
  Button,
  Card,
  Checkbox,
  Col,
  Collapse,
  DatePicker,
  Descriptions,
  Divider,
  Dropdown,
  Empty,
  Form,
  Input,
  InputNumber,
  Layout,
  List,
  Menu,
  Modal,
  Popconfirm,
  Progress,
  Radio,
  Row,
  Select,
  Space,
  Spin,
  Tag
} from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import { authState, clearAuth, initializeAuth } from './stores/auth'

const Home = () => import('./views/Home.vue')
const Result = () => import('./views/Result.vue')
const Trips = () => import('./views/Trips.vue')
const Login = () => import('./views/Login.vue')
const Register = () => import('./views/Register.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Home',
      component: Home,
      meta: { requiresAuth: true }
    },
    {
      path: '/result',
      redirect: () => {
        const tripId = sessionStorage.getItem('activeTripId')
        return tripId ? `/trips/${tripId}` : '/trips'
      },
      meta: { requiresAuth: true }
    },
    {
      path: '/trips',
      name: 'Trips',
      component: Trips,
      meta: { requiresAuth: true }
    },
    {
      path: '/trips/:tripId',
      name: 'TripResult',
      component: Result,
      meta: { requiresAuth: true }
    },
    {
      path: '/login',
      name: 'Login',
      component: Login,
      meta: { guestOnly: true }
    },
    {
      path: '/register',
      name: 'Register',
      component: Register,
      meta: { guestOnly: true }
    }
  ]
})

router.beforeEach(async (to) => {
  await initializeAuth()

  if (to.meta.requiresAuth && !authState.user) {
    return {
      name: 'Login',
      query: { redirect: to.fullPath }
    }
  }

  if (to.meta.guestOnly && authState.user) {
    return { name: 'Home' }
  }
})

const app = createApp(App)

window.addEventListener('auth:unauthorized', () => {
  clearAuth()
  if (router.currentRoute.value.name !== 'Login') {
    void router.replace({
      name: 'Login',
      query: { redirect: router.currentRoute.value.fullPath }
    })
  }
})

app.use(router)
for (const component of [
  Affix, Alert, BackTop, Button, Card, Checkbox, Col, Collapse, DatePicker,
  Descriptions, Divider, Dropdown, Empty, Form, Input, InputNumber, Layout,
  List, Menu, Modal, Popconfirm, Progress, Radio, Row, Select, Space, Spin, Tag
]) {
  app.use(component as Plugin)
}

app.mount('#app')
