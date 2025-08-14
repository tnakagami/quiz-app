## Preparation
### Update config
Open the [config/Doxyfile](./config/Doxyfile) and modify the following elements.

| Target | Example |
| :---- | :---- |
| `PROJECT_NUMBER` | 0.9.0 |
| `LATEX_CMD_NAME` | `pdflatex`, `platex`, etc. |
| `LATEX_EXTRA_STYLESHEET` | `doxygenext.sty`, `hyperlinkfix.sty`, etc. |

### Build
Run the following command to build related images.

```bash
./wrapper.sh doxygen build
```

## Compile
1. Enter the container environment by typing the following command.

    ```bash
    # In the host environemnt
    ./wrapper.sh doxygen start
    docker exec -it doxygen.quiz-app bash
    ```

1. Execute the following command to create `html` files and `latex` files.

    ```bash
    # In the container environemnt
    ./config/compile-latex.sh
    ```