# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added 
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [0.2.0] - 2020-01-14

### Removed
- Removed internal session handling as it was in the way of optimizing running several actions
directly after each other. Instead now you need to call `client.startup()` in the
beginning and `client.shutdown()` when you are done. 

## [0.1.2] - 2020-01-14

### Changed
-  Separated value identification in parsing config for the different databases so that 
it is possible to know if for example an average value is the monthly or hourly average.  

## [0.1.1] - 2020-01-08

### Fixed
- Fixed error in setup.py that listed the wrong dependency. (attr instead of attrs)

## [0.1.0] - 2020-01-08 [YANKED]

### Added
- Initial implementation of reading and writing data to Corus device.