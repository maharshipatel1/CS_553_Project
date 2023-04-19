import socket
import select
import errno
import sys

MAX_EVENTS = 100
BUFFER = 1024
EXIT = 1
HOST = socket.gethostbyname(socket.gethostname())  # Get the IP address of the current machine
PORT = 8033
RESPONSE = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\nHello, world!\r\n"

# Creating a new server socket for this backend server
try: 
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
except socket.error as e: 
    print ("Error CREATING socket: {}".format(e)) 
    sys.exit(1)

# Binding the socket to a specific address and port
try: 
    server_socket.bind((HOST, PORT))
except socket.error as e: 
    print ("Error BINDING socket: {}".format(e)) 
    sys.exit(1)

# Listening for incoming connections from the load balancer
try: 
    server_socket.listen(100)
except socket.error as e: 
    print ("Error LISTENING socket: {}".format(e)) 
    sys.exit(1)

print("Server is listening at IP: {} Port: {}....".format(HOST,PORT))
print("\n")

# Creating an epoll instance
try:
    epoll = select.epoll()
    epoll.register(server_socket.fileno(), select.EPOLLIN)
except OSError as e:
    print("Error in epoll instance: {}".format(e))
    sys.exit(1)

# The main execution of the server
try:
    connections = {}
    while True:
        
        # Setting the number of max connections
        try:
            events = epoll.poll(MAX_EVENTS)
        except OSError as e:
            print ("Error NO ready events: {}".format(e)) 
            sys.exit(1)
            
        for fileno, event in events:
            
            # Handle new connections
            if fileno == server_socket.fileno():
                # onaccept(function) and choosing server and create connection to the selected server
                
                try:
                    client_connection, client_address = server_socket.accept()  
                except socket.error as e:
                    print("Can't establish connection with client: {}".format(e))

                # Setting the new connection as unblocking and adding it to the list of open connections
                client_connection.setblocking(0)
                client_fd = client_connection.fileno()
                epoll.register(client_fd, select.EPOLLIN)
                connections[client_fd] = client_connection

                print("New Client connection from {} on socket: {}".format(client_address,client_fd))

            # Handle incoming data from the load balancer
            elif event & select.EPOLLIN:
                
                data = b""
                while True:
                    
                    # Reading the incoming data from the load balancer
                    try:
                        chunk = connections[fileno].recv(BUFFER)
                        # exit from loop when all data is received
                        if not chunk:
                            break
                        data += chunk

                    except socket.error as e:
                        if e.errno == errno.EWOULDBLOCK:
                            break
                        else:
                            raise
                
                # If we successfully recieve data, then we forward it to the backend server
                if data:
                    print("Read Data: {}".format(data))
                    print("Sending Response....")
                    connections[fileno].send(RESPONSE)
                    epoll.modify(fileno, select.EPOLLOUT)
                    
            # Handle outgoing data from the backend server
            elif event & select.EPOLLOUT:
                # respond back to client
                # Handle outgoing data
                # try:
                    
                #     connections[fileno].sendall(RESPONSE)
                # except socket.error as e:
                #     if e.errno == errno.EWOULDBLOCK:
                #         pass
                #     else:
                #         raise
                print("Closing Connection with client on socket {}".format(fileno))
                connections[fileno].close()
                print("\n")
            
            # Handling connection hang up    
            elif event & select.EPOLLHUP:
                epoll.unregister(fileno)
                connections[fileno].close()
                del connections[fileno]

# Closing all of the allocated resources                
finally:
    epoll.unregister(server_socket.fileno())
    epoll.close()
    server_socket.close()
