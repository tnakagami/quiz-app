from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy
from io import TextIOWrapper
import csv

class CustomCSVFileValidator:
  ##
  # @brief Constructor of CustomCSVFileValidator
  # @param length_checker Check whether the length of each record is valid or not (Default: None)
  # @param record_checker Check whether the value of each record is valid or not (Default: None)
  # @param extractor      Extract specific columns in each record (Default: None)
  def __init__(self, length_checker=None, record_checker=None, extractor=None):
    default_length_checker = lambda row: True
    default_record_checker = lambda rows: (True, None)
    default_extractor = lambda row: tuple(row)
    self.length_checker = length_checker or default_length_checker
    self.record_checker = record_checker or default_record_checker
    self.extractor = extractor or default_extractor
    self.valid_data = []

  ##
  # @brief Filtering the record
  # @return Filtered row except blank
  def _filter(self, data):
    return [val for val in data if val != '']

  ##
  # @brief Validate csv file
  # @param csv_file Target CSV file
  # @param encoding File encoding
  # @param header Header exists or not (Exist: True, Not exist: False, Default: True)
  # @exception ValidationError Format is invalid
  # @exception ValidationError Failed to decode
  # @exception ValidationError Raise exception
  def validate(self, csv_file, encoding, header=True):
    self.valid_data = []

    try:
      idx = 0

      with TextIOWrapper(csv_file, encoding=encoding) as text_file:
        reader = csv.reader(text_file)
        records = []

        # Skip header if exists
        if header:
          next(reader)
        # Check record length and extract specific columns
        for idx, data in enumerate(reader, 1):
          row = self._filter(data)
          is_valid = self.length_checker(row)

          if not is_valid:
            raise ValidationError(
              gettext_lazy('The length in line %(idx)d is invalid.'),
              code='invalid_file',
              params={'idx': idx},
            )
          # Store the current row as valid data
          self.valid_data += [row]
          records += [self.extractor(row)]
        # Check specific columns
        is_valid, err = self.record_checker(records)

        if not is_valid:
          raise err
    except UnicodeDecodeError as ex:
      raise ValidationError(
        gettext_lazy('Failed to decode in line %(idx)d (Encoding: %(encoding)s).'),
        code='invalid_file',
        params={'idx': idx, 'encoding': str(ex.encoding)},
      )
    except (ValueError, TypeError, AttributeError) as ex:
      raise ValidationError(
        gettext_lazy('Raise exception: %(ex)s.'),
        code='has_error',
        params={'ex': str(ex)},
      )

  ##
  # @brief Get each record
  # @return list of valid data
  def get_record(self):
    return self.valid_data