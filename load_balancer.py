import sys
import socket
import select
import errno
import random
from itertools import cycle

HOST = socket.gethostbyname(socket.gethostname())  # Get the IP address of the current machine
PORT = 8030
MAX_EVENTS = 100
BUFFER = 1024
RESPONSE = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\nHello, world!\r\n"
SERVER_POOL = set(['128.6.4.101', '128.6.4.101','128.6.4.101', '128.6.4.101'])

ITER = cycle(SERVER_POOL)

# Definiton of our Round-Robin Policy
def round_robin(iter):
    # round_robin([A, B, C, D]) --> A B C D A B C D A B C D ...
    return next(iter)


class LoadBalancer(object):
    """ Load balancer.
    
    Flow Diagram:-
    Client Socket <-> map(Client Socket, Server Socket) <-> Server Socket
    
    Notes:-
    flow_table is a dictionary that stores the mapping from the client socket to the server side socket
    sockets is a list that stores the currently connected and open server side sockets
    """

    flow_table = dict()
    sockets = list()
    
    # Initializng the attributes of our load balancer
    def __init__(self, algorithm='random'):
    
        self.algorithm = algorithm
        
        # Creating the load balancer's socket
        try: 
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
        except socket.error as e: 
            print ("Error CREATING socket: {}".format(e)) 
            sys.exit(1)

        # Binding the socket to a specific address and port
        try: 
            self.server_socket.bind((HOST, PORT))
        except socket.error as e: 
            print ("Error BINDING socket: {}".format(e)) 
            sys.exit(1)

        # Listening for incoming connections
        try: 
            self.server_socket.listen(100)
        except socket.error as e: 
            print ("Error LISTENING socket: {}".format(e)) 
            sys.exit(1)


        print("Server is listening at IP: {} Port: {}....".format(HOST,PORT))
        print("\n")
        
        # Adding the newly created socket to the sockets list that select will use
        self.sockets.append(self.server_socket)
    
    # A function that handles all new incoming connections
    # new conncention can be from any side = client or backened server
    def new_connection(self):
    
        try:
            client_socket, client_address = self.server_socket.accept()  
        except socket.error as e:
            print("Can't establish connection with client: {}".format(e))

        # selecting a backend server (IP address) based on the selected algorithm
        server_ip = self.select_server(SERVER_POOL, self.algorithm)
        server_port = 8032
        
        # Creating a new server-side socket
        # Instantiating socket on load balancer in order to connect to the backend server
        ss_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        
        # Connecting the backend server
        try:
            ss_socket.connect((server_ip, server_port)) 
            print("Load balancer: {} <-> Server connected: {}".format(ss_socket.getsockname(),(socket.gethostbyname(server_ip), server_port)))
        except:
            print("Can't establish connection with the Backend Server {} ".format(server_ip))
            print("Closing Connection with client {} on socket {}".format(client_address,client_socket.fileno()))
            client_socket.close()
            return
        
        # Adding the newly created socket to the list of sockets so that select() can trigger the requests
        self.sockets.append(client_socket)
        self.sockets.append(ss_socket)
        
        # Populating the flow table and the (client socket, server socket) mapping
        self.flow_table[client_socket] = ss_socket
        self.flow_table[ss_socket] = client_socket

        
        print("New CLIENT connection from {} on socket: {}".format(client_address,client_socket.fileno()))
        print("New connection with BACKEND SERVER {} on socket: {}".format((server_ip,server_port),ss_socket.fileno()))

        
    # A function that handles incoming data on a socket
    def on_recv(self, sock, data):
        
        # incoming message = request from CLIENT -> we need to forward it to the selected server 
        # Stateful scenario -> Identify cookie from data here and take action accordingly
        
        send_to_socket = self.flow_table[sock]
        
        try:
            send_to_socket.send(data)
            print("Sending data to {} at {}".format(send_to_socket.getsockname(), send_to_socket.getpeername()))
        except socket.error as e:
            if e.errno == errno.EWOULDBLOCK:
                pass
            else:
                raise
                
    # A function that handles closing a connection
    def on_close(self, sock):
        
        # Getting the closed socket from the mapping
        ss_socket = flow_table[sock]
        
        # Removing both sockets from the list of sockets so that they don't interfere with the select()
        self.sockets.remove(sock)
        self.sockets.remove(ss_sock)
        
        # Finally closing the sockets
        sock.close()
        ss_socket.close()
        
        # Clearing the flow table entry
        del self.flow_table[sock]
        del self.flow_table[ss_sock]
           
    # A function that selects a backend server based on the selected policy    
    def select_server(self, server_list, algorithm):
        if algorithm == 'random':
            return random.choice(server_list)
        elif algorithm == 'round robin':
            return round_robin(ITER)
        else:
            raise Exception('unknown algorithm: {}'.format(algorithm))


    # The main exectution of the load balancer
    def start(self):
        try:
        
            while True:
                
                # Creating the select instance
                read_list, write_list, exception_list = select.select(self.sockets, [], [])
                
                # When there is socket in the read list
                for sock in read_list:
                    
                    # Check if it is a new connection
                    if sock == self.server_socket:
                        
                        self.new_connection()
                        break
                    
                    # If it is a message from an already connected client
                    else:
                        
                        try:
                            data = sock.recv(BUFFER)
                            
                            # If we successfully recieved data
                            if data:
                                self.on_recv(sock, data)
                            # If no data is received then closing the socket
                            else:
                                self.on_close(sock)
                                break
                       
                        except:
                            self.on_close(sock)
                            break
        
        # Closing all the allocated resources
        finally:
            self.server_socket.close()

    

if __name__ == '__main__':
    
    try:
        LoadBalancer('round robin').start()
    except KeyboardInterrupt:
        print ("Ctrl C - Stopping load_balancer")
        sys.exit(1)
