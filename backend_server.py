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


# Creating a list of connections that select() can trigger when a connection is recieved
connections = list()
connections.append(server_socket)

# The main execution of the server
try:
    while True:
                
        # Creating the select instance
        read_list, write_list, exception_list = select.select(connections, [], [])
            
        for sock in read_list:
            
            # Handle new connections
            if sock == server_socket:
                # onaccept(function) and choosing server and create connection to the selected server
                
                try:
                    client_connection, client_address = server_socket.accept()  
                except socket.error as e:
                    print("Can't establish connection with client: {}".format(e))

                # Adding the client connection to the list of open connections
                connections.append(client_connection)

                print("New Client connection from {}".format(client_address))

            # Handle incoming data from the load balancer
            else:
                
                while True:
                    
                    # Reading the incoming data from the load balancer
                    try:
                        data = sock.recv(BUFFER)
                                
                        # If we successfully recieved data, then we print it and send the response back to the load balancer
                        if data:
                            print(data)
                            sock.send(RESPONSE)
                            print("Sending data from {} to {}".format(sock.getsockname(), sock.getpeername()))
                                
                        # If no data is received then closing the socket
                        else:
                            # Removing the socket from the list of sockets so that they don't interfere with the select()
                            connections.remove(sock)
        
                            # Finally closing the socket
                            sock.close()
                            break
                       
                    except:
                        # Removing the socket from the list of sockets so that they don't interfere with the select()
                        connections.remove(sock)
        
                        # Finally closing the socket
                        sock.close()
                        break

# Closing all of the allocated resources                
finally:
    server_socket.close()
