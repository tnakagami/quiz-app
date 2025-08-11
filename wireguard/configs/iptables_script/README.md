## PostUp/PostDown Sample Configuration
### PostUp
1. If you want to address translate an access coming to port 8443 from **your global ip-address** to 10.100.0.3:8443 of **VPN access ip-address**, you would register the following command.

    ```bash
    iptables -t nat -A PREROUTING -p tcp -d your-global-ip --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
    ```

1. Next, setup IP masquerade.

    ```bash
    iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
    ```

1. Finally, save the above commands to `conf.up.d/01-routing-localnet.conf`.
   In other words, create the file which the following commands are included into as `conf.up.d/01-routing-localnet.conf`.

    ```bash
    iptables -t nat -A PREROUTING -p tcp -d your-global-ip --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
    iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
    ```

1. In addition, you can add the link to `dozzle` page too. Specifically, add the following command.

    ```bash
    iptables -t nat -A PREROUTING -p tcp -d your-arbitrary-local-ip --dport 8080 -j DNAT --to-destination 10.100.0.4:8080
    ```

### PostDown
Save the following commands to `conf.down.d/01-routing-localnet.conf`.

```bash
iptables -t nat -D PREROUTING -p tcp -d your-global-ip --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
# The following command (IP: your-arbitrary-local-ip, Port: 8080) is optional
iptables -t nat -D PREROUTING -p tcp -d your-arbitrary-local-ip --dport 8080 -j DNAT --to-destination 10.100.0.4:8080
iptables -t nat -D POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
```

## Examples
I assume that **your global ip-address** is `1.12.123.234/30`, the listen port is `8443`, **VPN access ip-address** is `10.100.0.3`, **DOZZLE access ip-address** is `10.100.3.4`, and **your arbitrary ip-address** is `10.64.128.5`.
In this case, you can define `conf.up.d/01-routing-localnet.conf` and `conf.down.d/01-routing-localnet.conf` as follows.

### PostUp
```bash
iptables -t nat -A PREROUTING -p tcp -d 1.12.123.234/30 --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
iptables -t nat -A PREROUTING -p tcp -d 10.64.128.5/32 --dport 8080 -j DNAT --to-destination 10.100.0.4:8080
iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
```

### PostDown
```bash
iptables -t nat -D PREROUTING -p tcp -d 1.12.123.234/30 --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
iptables -t nat -D PREROUTING -p tcp -d 10.64.128.5/32 --dport 8080 -j DNAT --to-destination 10.100.0.4:8080
iptables -t nat -D POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
```