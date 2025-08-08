## PostUp/PostDown Sample Configuration
### PostUp
1. If you want to address translate an access coming to port 8443 from `your-global-ip` to 10.100.0.3:8443 of VPN client, you would register the following command.

    ```bash
    iptables -t nat -A PREROUTING -p tcp -d your-global-ip --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
    ```

1. Next, setup IP masquerade.

    ```bash
    iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
    ```

1. Finally, save the above command in `conf.up.d/01-routing-localnet.conf`.
   In other words, save the following command to `conf.up.d/01-routing-localnet.conf`.

    ```bash
    iptables -t nat -A PREROUTING -p tcp -d your-global-ip --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
    iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
    ```

### PostDown
Save the following command in `conf.down.d/01-routing-localnet.conf`.

```bash
iptables -t nat -D PREROUTING -p tcp -d your-global-ip --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
iptables -t nat -D POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
```

## Examples
I assume that `your-global-ip` is `1.12.123.234/30`, the listen port is `8443`, and VPN client ip is `10.100.0.3`.
In this case, you can define `conf.up.d/01-routing-localnet.conf` and `conf.down.d/01-routing-localnet.conf` as follows.

### PostUp
```bash
iptables -t nat -A PREROUTING -p tcp -d 1.12.123.234/30 --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
```

### PostDown
```bash
iptables -t nat -D PREROUTING -p tcp -d 1.12.123.234/30 --dport 8443 -j DNAT --to-destination 10.100.0.3:8443
iptables -t nat -D POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
```