from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy
from io import TextIOWrapper
import csv
import uuid

class CustomCSVFileValidator:
  ##
  # @brief Constructor of CustomCSVFileValidator
  # @param length_checker Check whether the length of each record is valid or not (Default: None)
  # @param record_checker Check whether the value of each record is valid or not (Default: None)
  # @param extractor      Extract specific columns in each record (Default: None)
  def __init__(self, length_checker=None, record_checker=None, extractor=None):
    default_length_checker = lambda row: True
    default_record_checker = lambda rows: None
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
        self.record_checker(records)
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

class CustomCSVDataValidator:
  ##
  # @brief Constructor of CustomCSVDataValidator
  # @param model_class Target model class
  # @param exception_field_name Field name when the exception is raised
  # @param base_qs Base queryset (Default: None)
  def __init__(self, model_class, exception_field_name, base_qs=None):
     self.model_class = model_class
     self.exception_field_name = str(exception_field_name)
     self.base_qs = base_qs or model_class.objects.all()

  ##
  # @brief Validate input data
  # @param input_set Input set
  # @param condition Filtering condition
  # @param field_name Extracted field name
  # @param specific_data Use specific data (Default: None)
  # @param use_uuid UUID is used or not (Used: True, Not used: False, Default: False)
  # @exception ValidationError Invalid input
  def validate(self, input_set, condition, field_name, specific_data=None, use_uuid=False):
    try:
      if use_uuid:
        # Check whetner target's pk is uuid or not
        for key in input_set:
          uuid.UUID(key)
    except (ValueError, AttributeError) as ex:
      raise ValidationError(
        gettext_lazy('The csv file includes invalid value(s). Details: %(value)s'),
        code='invalid_file',
        params={'value': str(ex)},
      )

    if specific_data is None:
      # Get target set based on database records
      targets = self.base_qs.filter(**{condition: list(input_set)}).values_list(field_name, flat=True)
      targets = {str(val) for val in targets}
    else:
      targets = specific_data
    # Calculate difference between original set and generated one based on database
    diff = input_set - targets
    # In the case of that difference exists.
    if diff:
      records = self.model_class.objects.filter(**{condition: list(diff)}).order_by(field_name)
      values = ','.join([str(instance) for instance in records])
      # Raise validation error
      raise ValidationError(
        gettext_lazy('The csv file includes invalid %(name)s(s). Details: %(values)s'),
        code='invalid_file',
        params={
          'name': self.exception_field_name,
          'values': values,
        },
      )