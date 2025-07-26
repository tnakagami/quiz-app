## PostUp/PostDown Sample Configuration
### PostUp
1. If you want to address translate an access coming to port 80 from 192.168.100.2 to 10.100.0.3:3002 of VPN client, you would register the following command.

    ```bash
    iptables -t nat -A PREROUTING -p tcp -d 192.168.100.2 --dport 80 -j DNAT --to-destination 10.100.0.3:3002
    ```

1. Next, setup IP masquerade.

    ```bash
    iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
    ```

1. Finally, save the above command in `conf.up.d/01-routing-localnet.conf`.
   In other words, save the following command to `conf.up.d/01-routing-localnet.conf`.

    ```bash
    iptables -t nat -A PREROUTING -p tcp -d 192.168.100.2 --dport 80 -j DNAT --to-destination 10.100.0.3:3002
    iptables -t nat -A POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
    ```

### PostDown
Save the following command in `conf.down.d/01-routing-localnet.conf`.

```bash
iptables -t nat -D PREROUTING -p tcp -d 192.168.100.2 --dport 80 -j DNAT --to-destination 10.100.0.3:3002
iptables -t nat -D POSTROUTING -d 10.100.0.0/24 -j MASQUERADE
```