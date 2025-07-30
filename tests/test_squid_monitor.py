#!/usr/bin/env python3
"""Unit tests for Squid Monitor"""

import unittest
import tempfile
import json
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import yaml

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from squid_monitor import Config, StateManager, ServiceMonitor, Logger


class TestConfig(unittest.TestCase):
    """Test configuration management"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def test_default_config(self):
        """Test loading default configuration"""
        config = Config()
        
        self.assertEqual(config.config['smtp']['server'], 'smtp.example.com')
        self.assertEqual(config.config['smtp']['port'], 25)
        self.assertEqual(config.config['monitoring']['service_name'], 'squid')
        
    def test_config_from_file(self):
        """Test loading configuration from YAML file"""
        config_file = os.path.join(self.temp_dir, 'test_config.yaml')
        test_config = {
            'smtp': {
                'server': 'test.smtp.com',
                'port': 587
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(test_config, f)
        
        config = Config(config_file)
        self.assertEqual(config.config['smtp']['server'], 'test.smtp.com')
        self.assertEqual(config.config['smtp']['port'], 587)
        
    def test_env_override(self):
        """Test environment variable override"""
        os.environ['SMTP_SERVER'] = 'env.smtp.com'
        os.environ['SMTP_PORT'] = '2525'
        
        config = Config()
        self.assertEqual(config.config['smtp']['server'], 'env.smtp.com')
        self.assertEqual(config.config['smtp']['port'], 2525)
        
        # Cleanup
        del os.environ['SMTP_SERVER']
        del os.environ['SMTP_PORT']
        
    def test_email_validation(self):
        """Test email address validation"""
        os.environ['SMTP_FROM'] = 'invalid-email'
        
        with self.assertRaises(ValueError):
            Config()
        
        # Cleanup
        del os.environ['SMTP_FROM']
        
    def test_multiple_recipients(self):
        """Test parsing multiple email recipients"""
        os.environ['SMTP_TO'] = 'user1@example.com,user2@example.com'
        
        config = Config()
        self.assertEqual(len(config.config['smtp']['to_addresses']), 2)
        self.assertIn('user1@example.com', config.config['smtp']['to_addresses'])
        self.assertIn('user2@example.com', config.config['smtp']['to_addresses'])
        
        # Cleanup
        del os.environ['SMTP_TO']


class TestStateManager(unittest.TestCase):
    """Test state management"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'test_state.json')
        self.state_manager = StateManager(self.state_file)
        
    def test_initial_state(self):
        """Test initial state creation"""
        self.assertIsNone(self.state_manager.state['last_check'])
        self.assertIsNone(self.state_manager.state['last_status'])
        self.assertEqual(self.state_manager.state['consecutive_failures'], 0)
        
    def test_state_persistence(self):
        """Test state save and load"""
        self.state_manager.state['last_check'] = datetime.now().isoformat()
        self.state_manager.state['last_status'] = True
        self.state_manager.save_state()
        
        # Load state in new instance
        new_manager = StateManager(self.state_file)
        self.assertTrue(new_manager.state['last_status'])
        self.assertIsNotNone(new_manager.state['last_check'])
        
    def test_should_send_alert_first_failure(self):
        """Test alert on first failure"""
        self.assertTrue(self.state_manager.should_send_alert(False, 3600))
        
    def test_should_send_alert_recovery(self):
        """Test alert on recovery"""
        self.state_manager.state['last_status'] = False
        self.assertTrue(self.state_manager.should_send_alert(True, 3600))
        
    def test_alert_cooldown(self):
        """Test alert cooldown period"""
        # Set last alert time
        self.state_manager.state['last_status'] = False
        self.state_manager.state['last_alert_time'] = datetime.now().isoformat()
        
        # Should not alert immediately
        self.assertFalse(self.state_manager.should_send_alert(False, 3600))
        
        # Should alert after cooldown
        old_time = datetime.now() - timedelta(seconds=3700)
        self.state_manager.state['last_alert_time'] = old_time.isoformat()
        self.assertTrue(self.state_manager.should_send_alert(False, 3600))
        
    def test_update_state(self):
        """Test state updates"""
        # Test failure
        self.state_manager.update_state(False, alert_sent=True)
        self.assertFalse(self.state_manager.state['last_status'])
        self.assertEqual(self.state_manager.state['consecutive_failures'], 1)
        self.assertIsNotNone(self.state_manager.state['last_alert_time'])
        
        # Test recovery
        self.state_manager.update_state(True, alert_sent=False)
        self.assertTrue(self.state_manager.state['last_status'])
        self.assertEqual(self.state_manager.state['consecutive_failures'], 0)
        self.assertIsNotNone(self.state_manager.state['last_success_time'])


class TestServiceMonitor(unittest.TestCase):
    """Test service monitoring functionality"""
    
    def setUp(self):
        self.config = Config()
        self.logger = Mock()
        self.state_manager = Mock()
        self.monitor = ServiceMonitor(self.config, self.logger, self.state_manager)
        
    @patch('subprocess.run')
    def test_check_service_status_active(self, mock_run):
        """Test checking active service"""
        mock_run.return_value = Mock(returncode=0, stdout='active')
        
        is_active, status = self.monitor.check_service_status('squid')
        
        self.assertTrue(is_active)
        self.assertEqual(status, 'active')
        mock_run.assert_called_once()
        
    @patch('subprocess.run')
    def test_check_service_status_inactive(self, mock_run):
        """Test checking inactive service"""
        mock_run.return_value = Mock(returncode=3, stdout='inactive')
        
        is_active, status = self.monitor.check_service_status('squid')
        
        self.assertFalse(is_active)
        self.assertEqual(status, 'inactive')
        
    @patch('subprocess.run')
    def test_check_service_timeout(self, mock_run):
        """Test service check timeout"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('systemctl', 10)
        
        is_active, status = self.monitor.check_service_status('squid')
        
        self.assertFalse(is_active)
        self.assertEqual(status, 'timeout')
        
    @patch('builtins.open', create=True)
    def test_get_system_stats(self, mock_open):
        """Test system statistics gathering"""
        # Mock /proc/stat
        stat_content = "cpu 100 0 100 300 0 0 0 0 0 0\n"
        # Mock /proc/meminfo
        meminfo_content = "MemTotal: 1000 kB\nMemAvailable: 400 kB\n"
        
        mock_open.side_effect = [
            MagicMock(read=lambda: stat_content, __enter__=lambda s: s, __exit__=lambda *args: None),
            MagicMock(read=lambda: [line + '\n' for line in meminfo_content.split('\n')[:-1]], 
                     readlines=lambda: [line + '\n' for line in meminfo_content.split('\n')[:-1]],
                     __enter__=lambda s: s, __exit__=lambda *args: None)
        ]
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Filesystem Size Used Avail Use% Mounted\n/dev/sda1 100G 60G 40G 60% /"
            )
            
            stats = self.monitor.get_system_stats()
            
            self.assertIn('cpu_usage', stats)
            self.assertIn('memory_usage', stats)
            self.assertEqual(stats['disk_usage'], '60%')
            
    @patch('subprocess.run')
    def test_get_recent_logs(self, mock_run):
        """Test retrieving recent service logs"""
        mock_logs = "Jan 01 00:00:00 server squid[1234]: Starting...\n"
        mock_run.return_value = Mock(returncode=0, stdout=mock_logs)
        
        logs = self.monitor.get_recent_logs('squid')
        
        self.assertEqual(logs, mock_logs)
        mock_run.assert_called_with(
            ['journalctl', '-u', 'squid', '-n', '50', '--no-pager'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
    def test_create_alert_content_failure(self):
        """Test creating failure alert content"""
        with patch.object(self.monitor, 'get_system_stats') as mock_stats:
            with patch.object(self.monitor, 'get_recent_logs') as mock_logs:
                mock_stats.return_value = {'cpu_usage': 50, 'memory_usage': 60, 'disk_usage': '70%'}
                mock_logs.return_value = "Test logs"
                
                subject, text, html = self.monitor.create_alert_content('squid', 'inactive', False)
                
                self.assertIn('[ALERT]', subject)
                self.assertIn('FAILURE', text)
                self.assertIn('#dc3545', html)  # Red color
                
    def test_create_alert_content_recovery(self):
        """Test creating recovery alert content"""
        with patch.object(self.monitor, 'get_system_stats') as mock_stats:
            with patch.object(self.monitor, 'get_recent_logs') as mock_logs:
                mock_stats.return_value = {'cpu_usage': 50, 'memory_usage': 60, 'disk_usage': '70%'}
                mock_logs.return_value = "Test logs"
                
                subject, text, html = self.monitor.create_alert_content('squid', 'active', True)
                
                self.assertIn('[RECOVERY]', subject)
                self.assertIn('RECOVERY', text)
                self.assertIn('#28a745', html)  # Green color
                
    @patch('smtplib.SMTP')
    def test_send_email_alert(self, mock_smtp):
        """Test sending email alerts"""
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        result = self.monitor.send_email_alert('Test Subject', 'Test Body', '<html>Test</html>')
        
        self.assertTrue(result)
        mock_server.send_message.assert_called_once()
        
    def test_send_email_alert_dry_run(self):
        """Test email sending in dry run mode"""
        self.monitor.config['features']['dry_run'] = True
        
        result = self.monitor.send_email_alert('Test Subject', 'Test Body', '<html>Test</html>')
        
        self.assertTrue(result)
        # Logger should be called for dry run
        self.logger.log.assert_called()
        
    @patch('smtplib.SMTP')
    def test_send_email_retry(self, mock_smtp):
        """Test email retry logic"""
        # First two attempts fail, third succeeds
        mock_smtp.return_value.__enter__.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            Mock()
        ]
        
        with patch('time.sleep'):  # Don't actually sleep in tests
            result = self.monitor.send_email_alert('Test Subject', 'Test Body', '<html>Test</html>')
        
        # Should still fail after retries
        self.assertFalse(result)
        self.assertEqual(mock_smtp.call_count, 3)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = os.path.join(self.temp_dir, 'state.json')
        os.environ['STATE_FILE'] = self.state_file
        os.environ['DRY_RUN'] = 'true'
        os.environ['LOG_LEVEL'] = 'ERROR'  # Reduce noise in tests
        
    def tearDown(self):
        # Cleanup environment
        for key in ['STATE_FILE', 'DRY_RUN', 'LOG_LEVEL']:
            if key in os.environ:
                del os.environ[key]
                
    @patch('subprocess.run')
    def test_full_monitoring_cycle(self, mock_run):
        """Test complete monitoring cycle"""
        # Service is down
        mock_run.return_value = Mock(returncode=3, stdout='inactive')
        
        config = Config()
        logger = Logger(config.config)
        state_manager = StateManager(self.state_file)
        monitor = ServiceMonitor(config, logger, state_manager)
        
        # First check - should alert
        with patch.object(monitor, 'send_email_alert', return_value=True) as mock_email:
            monitor.run_check()
            mock_email.assert_called_once()
            
        # Verify state was updated
        self.assertFalse(state_manager.state['last_status'])
        self.assertEqual(state_manager.state['consecutive_failures'], 1)
        
        # Second check - should not alert (cooldown)
        with patch.object(monitor, 'send_email_alert') as mock_email:
            monitor.run_check()
            mock_email.assert_not_called()
            
        # Service recovers
        mock_run.return_value = Mock(returncode=0, stdout='active')
        
        # Recovery check - should alert
        with patch.object(monitor, 'send_email_alert', return_value=True) as mock_email:
            monitor.run_check()
            mock_email.assert_called_once()
            
        # Verify state was updated
        self.assertTrue(state_manager.state['last_status'])
        self.assertEqual(state_manager.state['consecutive_failures'], 0)


if __name__ == '__main__':
    unittest.main()