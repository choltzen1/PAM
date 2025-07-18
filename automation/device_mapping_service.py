#!/usr/bin/env python3
import sys
import os
sys.path.append('C:\Users\DZhang8\OneDrive - T-Mobile USA\Documents\promo-app')

from device_mapping_updater import DeviceMappingUpdater

if __name__ == "__main__":
    updater = DeviceMappingUpdater()
    updater.schedule_daily_updates()
