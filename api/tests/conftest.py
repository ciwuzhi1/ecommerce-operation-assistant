"""测试只使用临时内存库，不连接 .env 中配置的 MySQL。"""
import os

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['APP_ENV'] = 'development'
os.environ['AUTH_SECRET_KEY'] = 'course-test-secret-not-for-deployment'
