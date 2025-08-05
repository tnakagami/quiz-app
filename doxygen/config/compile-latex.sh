#!/bin/bash

readonly DOXYGEN_CMD=/usr/local/bin/doxygen
readonly DOXYGEN_CONFIG=/doxygen/config/Doxyfile
readonly OUTPUT_DIR=/doxygen/output
readonly LATEX_DIR=${OUTPUT_DIR}/latex

# Remove old documents
rm -rf ${OUTPUT_DIR}/*

# Create documents
${DOXYGEN_CMD} ${DOXYGEN_CONFIG}

# =======================
# Move to latex directory
# =======================
pushd ${LATEX_DIR}

# Replace documentclass's option
latex_cmd=$(cat ${DOXYGEN_CONFIG} | perl -ne 'print if /(?<=LATEX_CMD_NAME)\s*=\s*([a-z]+).*$/' | awk '{print $3;}')
# If the user uses `platex` command, then the system replace "twoside" of documentclass's option to "twoside,dvipdfmx".
if [ -n ${latex_cmd} ] && [ "${latex_cmd}" != "pdflatex" ]; then
  sed -i -e "s/\[twoside\]/\[twoside,dvipdfmx\]/" refman.tex
  use_dvipdfmx=1
else
  use_dvipdfmx=0
fi

# Modify `longtabu*` command. Specifically, replace its command to `longtable` command
mv doxygen.sty old-doxygen.sty
perl <<- _EOF_ > doxygen.sty
open(IN, "old-doxygen.sty") or die "Can't open file.\n";
# Read line
while (<IN>) {
  # If longtabu command exists
  if (\$_ =~ /longtabu/) {
    # if the command includes "begin"
    if (\$_ =~ /begin/) {
      # Count the number of pipes
      \$pipe_count = (() = \$_ =~ m/\|/g);
      # Replace "\begin{longtabu*}spread 0pt [l]{|***|***|......|***|}" to "\begin{longtable}{|***|***|......|***|}"
      \$after = "longtable}{" . ("|c" x (\$pipe_count - 1));
      (\$output = \$_) =~ s/longtabu\*\}.*(?=\|\})/\$after/;
    }
    # if the command includes "end"
    else {
      # Replace "longtabu*" to "longtable"
      (\$output = \$_) =~ s/longtabu\*/longtable/;
    }
    print \$output;
  }
  else {
    print;
  }
}
close(IN);
_EOF_

# Compile latex
make
# Create pdf
if [ ${use_dvipdfmx} -eq 1 ]; then
  dvipdfmx refman.dvi
fi

popd